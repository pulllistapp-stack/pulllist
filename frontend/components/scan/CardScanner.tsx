"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  Loader2,
  RotateCcw,
  ScanLine,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import { useCollection } from "@/components/CollectionProvider";
import { RarityChip } from "@/components/RarityChip";
import { scanCard, type ScanCandidate, type ScanResponse } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Phase =
  | "idle"        // before camera starts
  | "ready"       // camera streaming, waiting for capture
  | "captured"    // image frozen, user can retry or identify
  | "identifying" // POSTing to backend
  | "result"      // got candidates back
  | "error";

export function CardScanner() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const { toggle: toggleCollection, has: ownsCard } = useCollection();
  const [adding, setAdding] = useState<string | null>(null);

  // Start camera on mount
  useEffect(() => {
    void startCamera();
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startCamera = async () => {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" }, // back camera on phones
          width: { ideal: 1280 },
          height: { ideal: 1920 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setPhase("ready");
    } catch (e) {
      setErr(
        e instanceof Error
          ? `Camera not available: ${e.message}. Try the file upload fallback.`
          : "Camera not available",
      );
      setPhase("error");
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  const capture = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    setCapturedImage(dataUrl);
    setPhase("captured");
    stopCamera();
  };

  const retry = () => {
    setCapturedImage(null);
    setResult(null);
    setErr(null);
    void startCamera();
  };

  const identify = async () => {
    if (!capturedImage) return;
    setPhase("identifying");
    setErr(null);
    try {
      const res = await scanCard(capturedImage, "image/jpeg");
      setResult(res);
      setPhase("result");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Scan failed");
      setPhase("error");
    }
  };

  const onFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setCapturedImage(reader.result as string);
      setPhase("captured");
      stopCamera();
    };
    reader.readAsDataURL(file);
  };

  const addToCollection = async (cardId: string) => {
    setAdding(cardId);
    try {
      await toggleCollection(cardId);
    } finally {
      setAdding(null);
    }
  };

  return (
    <div className="relative mx-auto w-full max-w-2xl">
      {/* Live camera / captured view */}
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-3xl bg-black shadow-xl">
        {/* Live video */}
        {!capturedImage && (
          <>
            <video
              ref={videoRef}
              playsInline
              muted
              autoPlay
              className="absolute inset-0 h-full w-full object-cover"
            />
            {/* Targeting overlay — Pokémon card aspect ratio guide */}
            {phase === "ready" && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="relative aspect-[245/342] w-3/4 rounded-2xl border-2 border-dashed border-white/60 shadow-[0_0_0_9999px_rgba(0,0,0,0.45)]">
                  <span className="absolute -top-8 left-1/2 -translate-x-1/2 text-xs font-mono uppercase tracking-widest text-white/90">
                    Align card here
                  </span>
                </div>
              </div>
            )}
          </>
        )}

        {/* Captured still */}
        {capturedImage && (
          <Image
            src={capturedImage}
            alt="Captured card"
            fill
            className="object-cover"
            unoptimized
          />
        )}

        {/* Hidden canvas for capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Loading overlay */}
        {phase === "identifying" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm text-white">
            <Loader2 className="h-10 w-10 animate-spin mb-3 text-accent-yellow" />
            <p className="text-sm font-semibold">Identifying card…</p>
            <p className="mt-1 text-xs text-white/60 font-mono">
              Claude Vision · ~2-3s
            </p>
          </div>
        )}

        {/* Error overlay */}
        {phase === "error" && err && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm text-white p-6 text-center">
            <AlertCircle className="h-10 w-10 mb-3 text-accent-red" />
            <p className="text-sm font-semibold mb-2">Couldn&apos;t scan</p>
            <p className="text-xs text-white/70 mb-4 max-w-xs">{err}</p>
            <button
              onClick={retry}
              className="rounded-full bg-white text-gray-900 font-bold px-4 py-2 text-sm hover:brightness-95"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {/* Action bar */}
      <div className="mt-4 flex items-center justify-center gap-3">
        {phase === "ready" && (
          <>
            <button
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-surface px-4 py-2.5 text-sm font-semibold text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary transition-colors"
              title="Upload an image instead"
            >
              <Upload className="h-4 w-4" />
              Upload
            </button>
            <button
              onClick={capture}
              className="inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-extrabold px-7 py-3 text-base hover:brightness-105 shadow-lg shadow-accent-yellow/40 transition-all"
            >
              <ScanLine className="h-5 w-5" />
              Capture
            </button>
          </>
        )}

        {phase === "captured" && (
          <>
            <button
              onClick={retry}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-bg-surface px-4 py-2.5 text-sm font-semibold text-text-secondary hover:text-text-primary transition-colors"
            >
              <RotateCcw className="h-4 w-4" />
              Retry
            </button>
            <button
              onClick={identify}
              className="inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-extrabold px-7 py-3 text-base hover:brightness-105 shadow-lg shadow-accent-yellow/40 transition-all"
            >
              <Sparkles className="h-5 w-5" />
              Identify card
            </button>
          </>
        )}

        {phase === "result" && (
          <button
            onClick={retry}
            className="inline-flex items-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-extrabold px-5 py-2.5 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
          >
            <Camera className="h-4 w-4" />
            Scan another
          </button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onFileUpload}
          className="hidden"
        />
      </div>

      {/* Result panel */}
      {phase === "result" && result && (
        <div className="mt-6 rounded-3xl border border-border bg-bg-surface p-5">
          {/* Identification summary */}
          <div className="mb-4 flex items-center gap-3">
            <ConfidenceBadge confidence={result.identification.confidence} />
            <div className="min-w-0">
              <p className="font-bold text-text-primary truncate">
                {result.identification.card_name ?? "Couldn't read card name"}
              </p>
              <p className="text-xs text-text-tertiary font-mono">
                {result.identification.set_name ?? "?"} ·{" "}
                {result.identification.card_number ?? "#?"}
              </p>
            </div>
          </div>

          {result.identification.notes && (
            <p className="mb-4 rounded-xl bg-bg/60 border border-border/60 p-3 text-xs text-text-secondary leading-relaxed">
              <span className="font-mono uppercase tracking-wider text-text-tertiary">
                Notes:
              </span>{" "}
              {result.identification.notes}
            </p>
          )}

          {/* Candidates */}
          {result.candidates.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-border bg-bg/40 p-6 text-center">
              <X className="mx-auto h-8 w-8 text-text-tertiary mb-2" />
              <p className="text-sm font-medium text-text-primary">
                No matching cards in our catalog
              </p>
              <p className="mt-1 text-xs text-text-tertiary">
                The card may not be indexed yet — try a different angle or
                let us know.
              </p>
            </div>
          ) : (
            <>
              <p className="mb-2 text-xs font-mono uppercase tracking-wider text-text-tertiary">
                {result.candidates.length === 1
                  ? "Match"
                  : `${result.candidates.length} possible matches — pick one`}
              </p>
              <div className="space-y-2">
                {result.candidates.map((c) => (
                  <CandidateCard
                    key={c.id}
                    candidate={c}
                    isOwned={ownsCard(c.id)}
                    isAdding={adding === c.id}
                    onAdd={() => addToCollection(c.id)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ConfidenceBadge({
  confidence,
}: {
  confidence: "high" | "medium" | "low";
}) {
  const cls = {
    high: "bg-accent-green/15 text-accent-green border-accent-green/40",
    medium: "bg-amber-500/15 text-amber-500 border-amber-500/40",
    low: "bg-accent-red/15 text-accent-red border-accent-red/40",
  }[confidence];
  return (
    <span
      className={cn(
        "shrink-0 inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider font-mono",
        cls,
      )}
    >
      {confidence}
    </span>
  );
}

function CandidateCard({
  candidate,
  isOwned,
  isAdding,
  onAdd,
}: {
  candidate: ScanCandidate;
  isOwned: boolean;
  isAdding: boolean;
  onAdd: () => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-bg p-3 transition-colors hover:border-accent-yellow/40">
      <Link
        href={`/cards/${candidate.id}`}
        className="relative h-20 w-14 shrink-0 overflow-hidden rounded-md bg-bg-surface"
      >
        {candidate.image_small ? (
          <Image
            src={candidate.image_small}
            alt={candidate.name}
            fill
            className="object-contain"
            sizes="56px"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-text-tertiary">
            no img
          </div>
        )}
      </Link>
      <div className="min-w-0 flex-1">
        <Link
          href={`/cards/${candidate.id}`}
          className="truncate block text-sm font-bold text-text-primary hover:text-accent-yellow transition-colors"
        >
          {candidate.name}
        </Link>
        <p className="text-xs text-text-tertiary font-mono truncate">
          {candidate.set_name} · #{candidate.number ?? "—"}
        </p>
        <div className="mt-1.5 flex items-center gap-1.5">
          {candidate.rarity && <RarityChip rarity={candidate.rarity} />}
          {candidate.market_price_usd != null && (
            <span className="text-xs font-mono text-accent-yellow font-bold">
              ${candidate.market_price_usd.toFixed(2)}
            </span>
          )}
        </div>
      </div>
      <button
        onClick={onAdd}
        disabled={isAdding}
        className={cn(
          "shrink-0 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold transition-colors",
          "disabled:opacity-50",
          isOwned
            ? "bg-accent-green/15 text-accent-green border border-accent-green/30"
            : "bg-accent-yellow text-gray-900 hover:brightness-105 shadow-sm shadow-accent-yellow/30",
        )}
      >
        {isAdding ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : isOwned ? (
          <>
            <CheckCircle2 className="h-3 w-3" />
            Owned
          </>
        ) : (
          <>+ Add</>
        )}
      </button>
    </div>
  );
}
