"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

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
import { scanCard, type ScanCandidate, type ScanResponse } from "@/lib/auth";
import {
  fetchPhashCatalog,
  fetchPhashCatalogStats,
  getCard,
  type PhashCatalogResponse,
} from "@/lib/api";
import {
  computePhash,
  extractFrameForHash,
  findNearest,
} from "@/lib/phash";

type Mode = "camera" | "confirm";

// Match threshold — hamming distance between a camera frame's pHash
// and a catalog hash. Backend uses 5 for cache lookups on identical
// re-scans; camera-vs-render is noisier (lighting / YUV / lens blur
// each contribute a few bits). Set to 26 — anything under produces a
// detection banner, anything above only surfaces as the diagnostic
// "closest" line so LO can see how far real matches are landing.
const BULK_MATCH_THRESHOLD = 26;

// After the user adds or skips a card, don't re-detect the same
// card_id for this many ms. Prevents an instant re-fire when the user
// hasn't physically moved the card yet.
const BULK_SKIP_TTL_MS = 6000;

// Auto-capture cadence. Slow enough that the pHash + JSON search
// stays off the render thread, fast enough that a stability window
// still lands within a few seconds of user holding still.
const BULK_TICK_MS = 700;

// Stability requirement — the SAME card_id must be the top-1 nearest
// match this many consecutive ticks before we surface a detection
// banner. Filters camera micro-movement / autofocus jitter that
// otherwise makes the banner flash a different card every 500 ms.
// 3 ticks at 700 ms = ~2.1 s of the user actually holding still.
const BULK_STABILITY_TICKS = 3;

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
  const [catalog, setCatalog] = useState<PhashCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogCoverage, setCatalogCoverage] = useState<number | null>(null);
  const [bulkDetected, setBulkDetected] = useState<BulkDetected | null>(null);
  const [bulkList, setBulkList] = useState<BulkListItem[]>([]);
  const [bulkAdding, setBulkAdding] = useState(false);
  // Diagnostic — the top-1 nearest catalog match every tick, whether
  // or not it clears BULK_MATCH_THRESHOLD. Lets us see what real
  // camera-vs-render distances look like so we can tune. The hash
  // field carries the actual camera-computed pHash so we can compare
  // it against the stored catalog value for the physical card LO is
  // pointing at.
  const [bulkClosest, setBulkClosest] = useState<{
    cardId: string;
    distance: number;
    hash: string;
  } | null>(null);
  // Stability tracking — last N tick outcomes, used to demand
  // consecutive matches before firing the detection banner.
  const stabilityRef = useRef<string[]>([]);
  // card_id → epoch ms until which we should ignore this card. Kept in
  // a ref so tick closure sees the latest without re-arming the
  // interval effect on every add / skip.
  const skipUntilRef = useRef<Map<string, number>>(new Map());
  const hashCanvasRef = useRef<HTMLCanvasElement | null>(null);

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
      const resp = await scanCard(b64, blob.type || "image/jpeg");
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

  // ── Bulk mode: lazy-load pHash catalog on first entry ──────────────
  // Guarded on catalog + error + loading so a failed fetch doesn't
  // re-arm the effect every re-render (previous version thrashed in a
  // loading → error → loading cycle when the endpoint 404'd).
  useEffect(() => {
    if (scanMode !== "bulk") return;
    if (catalog) return;
    if (catalogLoading) return;
    if (catalogError) return;
    setCatalogLoading(true);
    setCatalogError(null);
    Promise.all([fetchPhashCatalog(), fetchPhashCatalogStats()])
      .then(([cat, stats]) => {
        setCatalog(cat);
        const cov =
          stats.cards_with_image > 0
            ? stats.cards_with_phash / stats.cards_with_image
            : 0;
        setCatalogCoverage(cov);
      })
      .catch((e) => {
        console.error("[bulk] catalog fetch failed", e);
        setCatalogError(
          e instanceof Error ? e.message : "Unknown error loading catalog",
        );
      })
      .finally(() => setCatalogLoading(false));
  }, [scanMode, catalog, catalogLoading, catalogError]);

  const onBulkCatalogRetry = useCallback(() => {
    setCatalogError(null); // triggers the effect above to re-fire.
  }, []);

  // ── Bulk mode: auto-capture loop ───────────────────────────────────
  useEffect(() => {
    if (scanMode !== "bulk") return;
    if (!camera.ready || !catalog) return;
    if (bulkDetected) return; // pause polling while awaiting user action

    if (!hashCanvasRef.current) {
      hashCanvasRef.current = document.createElement("canvas");
    }
    const canvas = hashCanvasRef.current;
    let cancelled = false;
    let inFlight = false;

    const tick = async () => {
      if (cancelled || inFlight) return;
      const video = camera.videoRef.current;
      if (!video) return;
      const frame = extractFrameForHash(video, canvas);
      if (!frame) return;
      const hash = computePhash(frame);
      if (!hash) return;
      const match = findNearest(hash, catalog);
      if (!match) return;
      // Always publish the closest match for the diagnostic line —
      // gives LO immediate insight into what distances are typical.
      setBulkClosest({ cardId: match.cardId, distance: match.distance, hash });
      if (match.distance > BULK_MATCH_THRESHOLD) {
        // Miss — break the stability streak so a later match starts
        // counting fresh instead of piggy-backing on an old streak.
        stabilityRef.current = [];
        return;
      }
      const skipUntil = skipUntilRef.current.get(match.cardId);
      if (skipUntil && skipUntil > Date.now()) return;
      // Only fire the banner once the same card_id has been the
      // top-1 match for BULK_STABILITY_TICKS ticks in a row. Camera
      // micro-shakes otherwise flip the top match to whatever
      // similar-hash card slips ahead this frame.
      stabilityRef.current.push(match.cardId);
      if (stabilityRef.current.length > BULK_STABILITY_TICKS) {
        stabilityRef.current.shift();
      }
      const stable =
        stabilityRef.current.length >= BULK_STABILITY_TICKS &&
        stabilityRef.current.every((c) => c === match.cardId);
      if (!stable) return;
      // Fetch card details so the detection banner has name / price /
      // thumb. getCard hits our own catalog, no vision API involved.
      inFlight = true;
      try {
        const card = await getCard(match.cardId);
        if (cancelled) return;
        setBulkDetected({
          cardId: card.id,
          name: card.name,
          number: card.number,
          setName: card.set_name,
          imageUrl: card.image_small,
          priceUsd: card.market_price_usd,
          distance: match.distance,
        });
      } catch (e) {
        console.error("[bulk] getCard failed", e);
      } finally {
        inFlight = false;
      }
    };

    const interval = setInterval(tick, BULK_TICK_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [scanMode, camera.ready, camera.videoRef, catalog, bulkDetected]);

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
      stabilityRef.current = [];
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
    stabilityRef.current = [];
  }, [bulkDetected]);

  const onBulkClearList = useCallback(() => {
    setBulkList([]);
    skipUntilRef.current.clear();
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
      bulkCatalogLoading={catalogLoading}
      bulkCatalogError={catalogError}
      bulkCatalogCoverage={catalogCoverage}
      bulkDetected={bulkDetected}
      bulkClosest={bulkClosest}
      bulkList={bulkList}
      bulkAdding={bulkAdding}
      onBulkAdd={onBulkAdd}
      onBulkDismiss={onBulkDismiss}
      onBulkClearList={onBulkClearList}
      onBulkCatalogRetry={onBulkCatalogRetry}
    />
  );
}
