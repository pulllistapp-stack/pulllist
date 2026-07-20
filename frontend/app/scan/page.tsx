"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { useCamera } from "@/hooks/useCamera";
import {
  ScanCamera,
  type LastScanned,
  type ScanMode,
} from "@/components/scan/ScanCamera";
import type {
  BulkDetected,
  BulkListItem,
} from "@/components/scan/BulkScanPanel";
import {
  ScanConfirm,
  type MatchedCardForConfirm,
} from "@/components/scan/ScanConfirm";
import {
  createCollectionItem,
} from "@/lib/auth";
import {
  scanCard,
  scanEmbeddingMatch,
  type ScanCandidate,
  type ScanResponse,
  type VisionProvider,
} from "@/lib/auth";
import {
  computeEmbeddingFromCanvas,
  ensureEmbedModel,
  type EmbedProgress,
} from "@/lib/embedding";
import { computePhash, extractFrameForHash, hammingDistance } from "@/lib/phash";

type Mode = "camera" | "confirm";

// After the user adds or skips a card, don't re-detect the same
// card_id for this many ms. Prevents an instant re-fire when the user
// hasn't physically moved the card yet.
const BULK_SKIP_TTL_MS = 6000;

// Auto-capture cadence. pHash stability check itself is cheap (~10ms);
// slow enough here so we don't burn a Gemini call the moment the
// camera settles between shakes.
const BULK_TICK_MS = 500;

// Threshold above which we consider two frames "not stable enough".
// Set very permissively — real cameras drift ~30-35 bits even at
// rest. Anything below means the user isn't actively swiping past.
const BULK_STABILITY_HAMMING = 40;

// Number of consecutive stable ticks before we fire the vision call.
// 1 tick × 500 ms = fire on first stability signal.
const BULK_STABILITY_TICKS = 1;

// Safety net: if nothing has fired after this many ms of the
// capture loop running, fire anyway. Prevents "stuck at 'hold a
// card' forever" cases where whatever pHash the camera produces
// stays above the stability threshold.
const BULK_MAX_WAIT_MS = 6000;

// Abort a bulk vision call after this many ms. Gemini normally
// answers in 2-3 s; anything past 20 s is a Render cold start, a
// network stall, or a truly stuck request. We reset and let the
// next tick try again rather than sitting on "Reading card…"
// forever.
const BULK_SCAN_TIMEOUT_MS = 20000;

// Provider used ONLY for Gemini fallback when the CLIP embedding
// path's top match is below the confidence threshold or the model
// fails to load.
const BULK_VISION_PROVIDER: VisionProvider = "gemini";

// Cosine similarity above which we trust the CLIP embedding match
// without falling back to Gemini. CLIP-B/32 on real card photos
// typically lands 0.75+ for correct matches, 0.5-0.7 for
// plausibly-close, <0.5 for unrelated. Bias toward accepting.
const BULK_EMBEDDING_MIN_SIMILARITY = 0.72;

const LAST_SCAN_KEY = "pulllist:last_scanned";

function readLastScan(): LastScanned | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LAST_SCAN_KEY);
    return raw ? (JSON.parse(raw) as LastScanned) : null;
  } catch {
    return null;
  }
}

function writeLastScan(card: LastScanned): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LAST_SCAN_KEY, JSON.stringify(card));
  } catch {
    // localStorage full / private mode — silent fail
  }
}

function candidateToConfirm(
  c: ScanCandidate,
  language: string | null,
): MatchedCardForConfirm {
  return {
    cardId: c.id,
    name: c.name,
    number: c.number,
    setName: c.set_name,
    imageUrl: c.image_small,
    marketPriceUsd: c.market_price_usd,
    language,
  };
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      // "data:image/jpeg;base64,XXX" → "XXX"
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export default function ScanPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // A/B toggle: /scan?vision=gemini routes the shutter-based scan to
  // the Gemini endpoint instead of Claude. Default is Claude so the
  // production flow stays unchanged.
  const visionProvider: VisionProvider =
    searchParams?.get("vision") === "gemini" ? "gemini" : "claude";
  const { user, loading: authLoading } = useAuth();
  const camera = useCamera();

  const [mode, setMode] = useState<Mode>("camera");
  const [photoSrc, setPhotoSrc] = useState<string | null>(null);
  const [matched, setMatched] = useState<MatchedCardForConfirm | null>(null);
  const [scanResp, setScanResp] = useState<ScanResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [addedSuccess, setAddedSuccess] = useState(false);
  const [lastScanned, setLastScanned] = useState<LastScanned | null>(null);
  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Bulk mode ──────────────────────────────────────────────────────
  const [scanMode, setScanMode] = useState<ScanMode>("single");
  const [bulkDetected, setBulkDetected] = useState<BulkDetected | null>(null);
  const [bulkList, setBulkList] = useState<BulkListItem[]>([]);
  const [bulkAdding, setBulkAdding] = useState(false);
  const [bulkIdentifying, setBulkIdentifying] = useState(false);
  const [bulkIdentifyStartedAt, setBulkIdentifyStartedAt] = useState<
    number | null
  >(null);
  const [bulkScanCount, setBulkScanCount] = useState(0);
  const [bulkLastError, setBulkLastError] = useState<string | null>(null);
  // CLIP model download progress. Null before we start loading;
  // { progress: 0..1 } while downloading; ready object once loaded.
  const [embedModelProgress, setEmbedModelProgress] = useState<
    EmbedProgress | null
  >(null);
  const [embedModelReady, setEmbedModelReady] = useState(false);
  const [embedModelError, setEmbedModelError] = useState<string | null>(null);
  // Diagnostic — most recent frame-to-frame drift + running stable
  // count. Surfaced in the panel so LO can see whether stability
  // actually triggers on his phone or whether the threshold needs
  // more tuning. `forceScan` is a ref so the button handler can flip
  // it without re-arming the capture effect.
  const [bulkDiag, setBulkDiag] = useState<{
    drift: number | null;
    stableTicks: number;
    tickCount: number;
  }>({ drift: null, stableTicks: 0, tickCount: 0 });
  const stableTicksRef = useRef(0);
  const lastHashRef = useRef<string | null>(null);
  const forceScanRef = useRef(false);
  const loopStartRef = useRef<number>(0);
  // card_id → epoch ms until which we should ignore this card. Kept in
  // a ref so tick closure sees the latest without re-arming the
  // interval effect on every add / skip.
  const skipUntilRef = useRef<Map<string, number>>(new Map());
  const hashCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Hydrate last-scanned from localStorage on mount
  useEffect(() => {
    setLastScanned(readLastScan());
  }, []);

  // Auth gate
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login?redirect=/scan");
    }
  }, [authLoading, user, router]);

  // Start camera when entering camera mode; stop on confirm
  useEffect(() => {
    if (mode === "camera") {
      void camera.start();
    } else {
      camera.stop();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // Clean up object URLs + timers on unmount
  useEffect(() => {
    return () => {
      if (photoSrc && photoSrc.startsWith("blob:")) URL.revokeObjectURL(photoSrc);
      if (successTimer.current) clearTimeout(successTimer.current);
    };
  }, [photoSrc]);

  const runScan = async (blob: Blob) => {
    const previewUrl = URL.createObjectURL(blob);
    setPhotoSrc(previewUrl);
    setMode("confirm");
    setMatched(null);
    setScanResp(null);
    setScanning(true);

    try {
      const b64 = await blobToBase64(blob);
      const resp = await scanCard(b64, blob.type || "image/jpeg", visionProvider);
      setScanResp(resp);
      const pick =
        resp.candidates.find((c) => c.id === resp.matched_card_id) ??
        resp.candidates[0] ??
        null;
      if (pick) setMatched(candidateToConfirm(pick, null));
    } catch (e) {
      console.error(e);
      setMatched(null);
    } finally {
      setScanning(false);
    }
  };

  const onShutter = async () => {
    const blob = await camera.capture();
    if (!blob) return;
    await runScan(blob);
  };

  const onGalleryUpload = async (file: File) => {
    await runScan(file);
  };

  const onAdd = async ({
    variant,
    grader,
    condition,
    qty,
    pricePaidUsd,
  }: {
    variant: "normal" | "reverseHolofoil";
    grader: "Raw" | "PSA" | "BGS" | "CGC" | "TAG" | "AGS";
    condition: "NM" | "LP" | "MP" | "HP" | "DMG";
    qty: number;
    pricePaidUsd: number | null;
  }) => {
    if (!matched) return;
    setSubmitting(true);
    try {
      await createCollectionItem({
        card_id: matched.cardId,
        qty,
        variant,
        condition,
        is_graded: grader !== "Raw",
        // Grade value unknown until user goes to Edit modal post-add —
        // the grader brand alone goes in here so the row knows it's slabbed.
        grade: grader !== "Raw" ? grader : null,
        purchase_price_usd: pricePaidUsd,
      });

      const next: LastScanned = {
        cardId: matched.cardId,
        name: matched.name,
        number: matched.number,
        priceUsd: matched.marketPriceUsd,
        thumbUrl: matched.imageUrl,
      };
      setLastScanned(next);
      writeLastScan(next);

      setAddedSuccess(true);
      if (successTimer.current) clearTimeout(successTimer.current);
      successTimer.current = setTimeout(() => {
        setAddedSuccess(false);
        setMode("camera");
        setPhotoSrc(null);
        setMatched(null);
        setScanResp(null);
      }, 1800);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : "Add failed");
    } finally {
      setSubmitting(false);
    }
  };

  const onDiscard = () => {
    setMode("camera");
    setPhotoSrc(null);
    setMatched(null);
    setScanResp(null);
  };

  const onSearchManually = () => {
    const q = scanResp?.identification.card_name ?? matched?.name ?? "";
    router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  const onLastScannedTap = () => {
    if (lastScanned) router.push(`/cards/${lastScanned.cardId}`);
  };

  const onBulkCatalogRetry = useCallback(() => {
    // Legacy prop — no catalog fetch in the Gemini-backed flow. Kept
    // as a no-op so BulkScanPanel's error UI still compiles.
  }, []);

  // ── Bulk mode: lazy-load the CLIP embedding model ─────────────────
  // Only kicks in when the user actually opens Bulk. First-time
  // download is ~150 MB from the HuggingFace CDN; subsequent
  // sessions hit the browser cache. Model failures fall back to the
  // Gemini path further down the tick.
  useEffect(() => {
    if (scanMode !== "bulk") return;
    if (embedModelReady || embedModelError) return;
    let cancelled = false;
    setEmbedModelError(null);
    ensureEmbedModel((p) => {
      if (cancelled) return;
      setEmbedModelProgress(p);
    })
      .then(() => {
        if (!cancelled) setEmbedModelReady(true);
      })
      .catch((e) => {
        if (cancelled) return;
        console.error("[bulk] embed model load failed", e);
        setEmbedModelError(
          e instanceof Error ? e.message : String(e),
        );
      });
    return () => {
      cancelled = true;
    };
  }, [scanMode, embedModelReady, embedModelError]);

  // ── Bulk mode: auto-capture loop ───────────────────────────────────
  // Every tick: pHash the current frame, compare to previous. Two
  // consecutive stable ticks (~1 s of the user holding still)
  // capture a card-aspect crop, run it through the on-device CLIP
  // model (Xenova/clip-vit-base-patch32), and POST the 512-D
  // embedding to /scan/embedding-match. Backend serves the top-k
  // cosine-similarity nearest neighbours from the catalog matrix in
  // R2. If the top match's similarity clears the confidence bar we
  // trust it; otherwise we fall back to a Gemini call as a safety
  // net.
  useEffect(() => {
    if (scanMode !== "bulk") return;
    if (!camera.ready) return;
    if (bulkDetected || bulkIdentifying) return;

    if (!hashCanvasRef.current) {
      hashCanvasRef.current = document.createElement("canvas");
    }
    if (!captureCanvasRef.current) {
      captureCanvasRef.current = document.createElement("canvas");
    }
    const stabCanvas = hashCanvasRef.current;
    const captureCanvas = captureCanvasRef.current;
    let cancelled = false;
    let inFlight = false;
    let tickN = 0;
    loopStartRef.current = performance.now();

    const tick = async () => {
      if (cancelled || inFlight) return;
      const video = camera.videoRef.current;
      if (!video) return;
      tickN += 1;

      // Stability check — hash the frame, compare to the last one.
      const frame = extractFrameForHash(video, stabCanvas);
      if (!frame) return;
      const hash = computePhash(frame);
      if (!hash) return;

      const prev = lastHashRef.current;
      const drift = prev == null ? null : hammingDistance(prev, hash);
      if (drift != null && drift <= BULK_STABILITY_HAMMING) {
        stableTicksRef.current += 1;
      } else {
        stableTicksRef.current = 0;
      }
      lastHashRef.current = hash;
      setBulkDiag({
        drift,
        stableTicks: stableTicksRef.current,
        tickCount: tickN,
      });

      const forced = forceScanRef.current;
      if (forced) forceScanRef.current = false;
      const elapsed = performance.now() - loopStartRef.current;
      const timedOut = elapsed >= BULK_MAX_WAIT_MS;
      if (
        !forced &&
        !timedOut &&
        stableTicksRef.current < BULK_STABILITY_TICKS
      ) {
        return;
      }

      // Enough stability — build the card-aspect crop that both the
      // CLIP model and (as fallback) Gemini will see.
      const vw = video.videoWidth || 1280;
      const vh = video.videoHeight || 720;
      const CARD = 245 / 342;
      let cw = vw;
      let ch = vh;
      if (vw / vh > CARD) {
        ch = vh;
        cw = ch * CARD;
      } else {
        cw = vw;
        ch = cw / CARD;
      }
      cw *= 0.9;
      ch *= 0.9;
      const cx = (vw - cw) / 2;
      const cy = (vh - ch) / 2;
      // CLIP-B/32 expects 224 × 224 input. We draw the crop at that
      // exact size so the processor doesn't have to resize again and
      // JPEG-encoding cost drops for the fallback path.
      const outW = 224;
      const outH = 224;
      captureCanvas.width = outW;
      captureCanvas.height = outH;
      const ctx = captureCanvas.getContext("2d");
      if (!ctx) return;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(video, cx, cy, cw, ch, 0, 0, outW, outH);

      inFlight = true;
      setBulkIdentifying(true);
      setBulkIdentifyStartedAt(Date.now());
      setBulkLastError(null);
      const abortCtl = new AbortController();
      const timeoutId = window.setTimeout(
        () => abortCtl.abort(new Error("scan timeout")),
        BULK_SCAN_TIMEOUT_MS,
      );
      try {
        let matched: {
          id: string;
          name: string;
          number: string | null;
          set_name: string | null;
          image_small: string | null;
          market_price_usd: number | null;
        } | null = null;

        // Primary path — on-device CLIP embedding into R2 catalog
        // nearest-neighbour lookup. Sub-second when the model is
        // warm and the R2 index is loaded on the backend.
        if (embedModelReady) {
          const emb = await computeEmbeddingFromCanvas(captureCanvas);
          const embResp = await scanEmbeddingMatch(
            emb,
            3,
            abortCtl.signal,
          );
          setBulkScanCount((n) => n + 1);
          const top = embResp.matches[0] ?? null;
          if (top && top.similarity >= BULK_EMBEDDING_MIN_SIMILARITY) {
            matched = top;
          }
        }

        // Fallback — the CLIP model isn't loaded yet OR the top
        // similarity fell below the confidence bar. Gemini reads
        // the card text and is much more forgiving of foil / angle
        // edge cases at the cost of a $0.0001 API call.
        if (!matched) {
          const dataUrl = captureCanvas.toDataURL("image/jpeg", 0.85);
          const b64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
          const resp = await scanCard(
            b64,
            "image/jpeg",
            BULK_VISION_PROVIDER,
            abortCtl.signal,
          );
          setBulkScanCount((n) => n + 1);
          const pick = resp.candidates[0] ?? null;
          if (pick) matched = pick;
        }

        if (cancelled) return;
        if (!matched) {
          stableTicksRef.current = 0;
          return;
        }
        const skipUntil = skipUntilRef.current.get(matched.id);
        if (skipUntil && skipUntil > Date.now()) return;
        setBulkDetected({
          cardId: matched.id,
          name: matched.name,
          number: matched.number,
          setName: matched.set_name,
          imageUrl: matched.image_small,
          priceUsd: matched.market_price_usd,
          distance: 0,
        });
      } catch (e) {
        console.error("[bulk] scan attempt failed", e);
        const msg = e instanceof Error ? e.message : String(e);
        setBulkLastError(msg);
        stableTicksRef.current = 0;
        loopStartRef.current = performance.now();
      } finally {
        window.clearTimeout(timeoutId);
        inFlight = false;
        setBulkIdentifying(false);
        setBulkIdentifyStartedAt(null);
      }
    };

    const interval = setInterval(tick, BULK_TICK_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [
    scanMode,
    camera.ready,
    camera.videoRef,
    bulkDetected,
    bulkIdentifying,
    embedModelReady,
  ]);

  // ── Bulk mode: handlers ────────────────────────────────────────────
  const onBulkAdd = useCallback(async () => {
    if (!bulkDetected || bulkAdding) return;
    setBulkAdding(true);
    try {
      await createCollectionItem({
        card_id: bulkDetected.cardId,
        qty: 1,
        variant: "normal",
        condition: "NM",
        is_graded: false,
        grade: null,
        purchase_price_usd: null,
      });
      skipUntilRef.current.set(
        bulkDetected.cardId,
        Date.now() + BULK_SKIP_TTL_MS,
      );
      setBulkList((prev) => [
        {
          cardId: bulkDetected.cardId,
          name: bulkDetected.name,
          imageUrl: bulkDetected.imageUrl,
          priceUsd: bulkDetected.priceUsd,
          addedAt: Date.now(),
        },
        ...prev,
      ]);
      setBulkDetected(null);
      stableTicksRef.current = 0;
      lastHashRef.current = null;
    } catch (e) {
      console.error("[bulk] add failed", e);
      alert(e instanceof Error ? e.message : "Add failed");
    } finally {
      setBulkAdding(false);
    }
  }, [bulkDetected, bulkAdding]);

  const onBulkDismiss = useCallback(() => {
    if (!bulkDetected) return;
    // Same TTL as add so the next detection has to come from a real
    // card swap, not the same card sitting there.
    skipUntilRef.current.set(
      bulkDetected.cardId,
      Date.now() + BULK_SKIP_TTL_MS,
    );
    setBulkDetected(null);
    stableTicksRef.current = 0;
    lastHashRef.current = null;
  }, [bulkDetected]);

  const onBulkClearList = useCallback(() => {
    setBulkList([]);
    skipUntilRef.current.clear();
  }, []);

  const onBulkForceScan = useCallback(() => {
    forceScanRef.current = true;
    // Reset stability so the diagnostic shows an honest count after
    // the manual trigger fires.
    stableTicksRef.current = 0;
    setBulkDiag((d) => ({ ...d, stableTicks: 0 }));
  }, []);

  const onScanModeChange = useCallback((next: ScanMode) => {
    setScanMode(next);
    // Wipe any stale detection so switching modes doesn't leave a
    // ghost banner hanging on the other view.
    setBulkDetected(null);
  }, []);

  if (authLoading || !user) {
    return (
      <main className="mx-auto max-w-md px-4 py-16 text-center text-text-tertiary text-sm">
        Checking session…
      </main>
    );
  }

  if (mode === "confirm") {
    return (
      <ScanConfirm
        photoSrc={photoSrc ?? ""}
        matched={matched}
        scanning={scanning}
        addedSuccess={addedSuccess}
        submitting={submitting}
        onAdd={onAdd}
        onDiscard={onDiscard}
        onSearchManually={onSearchManually}
        onBack={onDiscard}
      />
    );
  }

  return (
    <ScanCamera
      videoRef={camera.videoRef}
      cameraReady={camera.ready}
      cameraError={camera.error}
      torchSupported={camera.torchSupported}
      torchOn={camera.torchOn}
      lastScanned={lastScanned}
      pendingCount={0}
      onShutter={onShutter}
      onGalleryUpload={onGalleryUpload}
      onTorchToggle={() => void camera.toggleTorch()}
      onFlipCamera={camera.flip}
      onBack={() => router.back()}
      onLastScannedTap={onLastScannedTap}
      scanMode={scanMode}
      onScanModeChange={onScanModeChange}
      bulkDetected={bulkDetected}
      bulkIdentifying={bulkIdentifying}
      bulkScanCount={bulkScanCount}
      bulkDrift={bulkDiag.drift}
      bulkStableTicks={bulkDiag.stableTicks}
      bulkTickCount={bulkDiag.tickCount}
      bulkIdentifyStartedAt={bulkIdentifyStartedAt}
      bulkLastError={bulkLastError}
      bulkModelReady={embedModelReady}
      bulkModelProgress={embedModelProgress}
      bulkModelError={embedModelError}
      bulkList={bulkList}
      bulkAdding={bulkAdding}
      onBulkAdd={onBulkAdd}
      onBulkDismiss={onBulkDismiss}
      onBulkClearList={onBulkClearList}
      onBulkForceScan={onBulkForceScan}
    />
  );
}
