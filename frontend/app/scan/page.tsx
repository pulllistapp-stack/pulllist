"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { useCamera } from "@/hooks/useCamera";
import {
  ScanCamera,
  type LastScanned,
} from "@/components/scan/ScanCamera";
import {
  ScanConfirm,
  type MatchedCardForConfirm,
} from "@/components/scan/ScanConfirm";
import {
  createCollectionItem,
} from "@/lib/auth";
import { scanCard, type ScanCandidate, type ScanResponse } from "@/lib/auth";

type Mode = "camera" | "confirm";

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
  const [flashOn, setFlashOn] = useState(false);
  const [photoSrc, setPhotoSrc] = useState<string | null>(null);
  const [matched, setMatched] = useState<MatchedCardForConfirm | null>(null);
  const [scanResp, setScanResp] = useState<ScanResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [addedSuccess, setAddedSuccess] = useState(false);
  const [lastScanned, setLastScanned] = useState<LastScanned | null>(null);
  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    grader,
    condition,
  }: {
    grader: "PSA" | "BGS" | "CGC" | "Raw";
    condition: "NM" | "LP" | "MP" | "HP" | "DMG";
  }) => {
    if (!matched) return;
    setSubmitting(true);
    try {
      await createCollectionItem({
        card_id: matched.cardId,
        qty: 1,
        condition,
        is_graded: grader !== "Raw",
        grade: grader !== "Raw" ? `${grader} ?` : null,
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
      flashOn={flashOn}
      lastScanned={lastScanned}
      pendingCount={0}
      onShutter={onShutter}
      onGalleryUpload={onGalleryUpload}
      onFlashToggle={() => setFlashOn((f) => !f)}
      onFlipCamera={camera.flip}
      onBack={() => router.back()}
      onLastScannedTap={onLastScannedTap}
    />
  );
}
