"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import {
  ChevronLeft,
  Image as ImageIcon,
  RotateCw,
  Sparkles,
  Zap,
  ZapOff,
} from "lucide-react";
import { useRef } from "react";

import { cn } from "@/lib/utils";
import { BulkScanPanel, type BulkDetected, type BulkListItem } from "./BulkScanPanel";

export type ScanMode = "single" | "bulk";

export type LastScanned = {
  cardId: string;
  name: string;
  number: string | null;
  priceUsd: number | null;
  thumbUrl: string | null;
};

type Props = {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  cameraReady: boolean;
  cameraError: string | null;
  torchSupported: boolean;
  torchOn: boolean;
  lastScanned: LastScanned | null;
  pendingCount: number;
  onShutter: () => void;
  onGalleryUpload: (file: File) => void;
  onTorchToggle: () => void;
  onFlipCamera: () => void;
  onBack: () => void;
  onLastScannedTap?: () => void;
  // Bulk mode — presentational shell renders the toggle + panel and
  // fires callbacks; parent runs the auto-capture loop + Gemini calls.
  scanMode: ScanMode;
  onScanModeChange: (mode: ScanMode) => void;
  bulkDetected: BulkDetected | null;
  bulkIdentifying: boolean;
  bulkScanCount: number;
  bulkDrift: number | null;
  bulkStableTicks: number;
  bulkTickCount: number;
  bulkList: BulkListItem[];
  bulkAdding: boolean;
  onBulkAdd: () => void;
  onBulkDismiss: () => void;
  onBulkClearList: () => void;
  onBulkForceScan: () => void;
};

function fmtPrice(v: number | null): string {
  if (v == null || v <= 0) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

/**
 * Camera viewfinder screen — Screen 1 of the kawaii scan flow.
 * Presentation only; the parent owns the camera stream + scan API.
 */
export function ScanCamera({
  videoRef,
  cameraReady,
  cameraError,
  torchSupported,
  torchOn,
  lastScanned,
  pendingCount,
  onShutter,
  onGalleryUpload,
  onTorchToggle,
  onFlipCamera,
  onBack,
  onLastScannedTap,
  scanMode,
  onScanModeChange,
  bulkDetected,
  bulkIdentifying,
  bulkScanCount,
  bulkDrift,
  bulkStableTicks,
  bulkTickCount,
  bulkList,
  bulkAdding,
  onBulkAdd,
  onBulkDismiss,
  onBulkClearList,
  onBulkForceScan,
}: Props) {
  const isBulk = scanMode === "bulk";
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openGalleryPicker = () => fileInputRef.current?.click();

  const onFilePicked: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const f = e.target.files?.[0];
    if (f) onGalleryUpload(f);
    // reset so picking the same file twice still fires
    e.target.value = "";
  };

  return (
    <div className="fixed inset-0 flex justify-center bg-[#FFF8E7] overflow-hidden">
      <div className="relative flex h-full w-full max-w-md flex-col overflow-hidden border-x border-[#FDE2C7] bg-[#FFF8E7] text-[#2D2A26]">
      {/* Header */}
      <header className="p-5 pt-[calc(1.25rem_+_env(safe-area-inset-top))] flex items-center justify-between relative z-10">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="w-10 h-10 rounded-full bg-white shadow-sm flex items-center justify-center border border-[#FDE2C7] hover:bg-[#FFF3DE] active:scale-95 transition"
        >
          <ChevronLeft className="w-6 h-6 text-[#2D2A26]" />
        </button>

        <div className="inline-flex rounded-full bg-white shadow-sm border border-[#FDE2C7] p-0.5">
          <button
            type="button"
            onClick={() => onScanModeChange("single")}
            className={cn(
              "rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wider transition-colors",
              scanMode === "single"
                ? "bg-[#FACC15] text-[#2D2A26] shadow-sm"
                : "text-[#8A7E72] hover:text-[#2D2A26]",
            )}
          >
            Single
          </button>
          <button
            type="button"
            onClick={() => onScanModeChange("bulk")}
            className={cn(
              "rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-wider transition-colors",
              scanMode === "bulk"
                ? "bg-[#FACC15] text-[#2D2A26] shadow-sm"
                : "text-[#8A7E72] hover:text-[#2D2A26]",
            )}
          >
            Bulk
          </button>
        </div>

        <button
          type="button"
          onClick={onTorchToggle}
          disabled={!torchSupported}
          aria-label={torchOn ? "Turn flash off" : "Turn flash on"}
          title={
            torchSupported
              ? torchOn
                ? "Flash on"
                : "Flash off"
              : "Flash not supported on this camera"
          }
          className={cn(
            "w-10 h-10 rounded-full shadow-sm flex items-center justify-center border transition active:scale-95",
            torchOn
              ? "bg-[#FACC15] border-[#FACC15]"
              : "bg-white border-[#FDE2C7]",
            !torchSupported && "opacity-40 cursor-not-allowed",
          )}
        >
          {torchOn ? (
            <Zap className="w-5 h-5 text-[#2D2A26] fill-[#2D2A26]" />
          ) : (
            <ZapOff className="w-5 h-5 text-[#8A7E72]" />
          )}
        </button>
      </header>

      {/* Viewfinder */}
      <main className="flex-1 min-h-0 px-5 flex flex-col items-center justify-start gap-5 relative z-10 overflow-y-auto overscroll-contain">
        <div className="relative w-full aspect-[3/4] bg-[#2D2A26]/5 rounded-[2rem] overflow-hidden border-4 border-white shadow-inner">
          {/* Live video stream */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="absolute inset-0 w-full h-full object-cover"
          />

          {/* Yellow corner brackets */}
          <div className="absolute inset-6 pointer-events-none">
            <div className="absolute -top-1 -left-1 w-10 h-10 border-t-[6px] border-l-[6px] border-[#FACC15] rounded-tl-[1.5rem]" />
            <div className="absolute -top-1 -right-1 w-10 h-10 border-t-[6px] border-r-[6px] border-[#FACC15] rounded-tr-[1.5rem]" />
            <div className="absolute -bottom-1 -left-1 w-10 h-10 border-b-[6px] border-l-[6px] border-[#FACC15] rounded-bl-[1.5rem]" />
            <div className="absolute -bottom-1 -right-1 w-10 h-10 border-b-[6px] border-r-[6px] border-[#FACC15] rounded-br-[1.5rem]" />
          </div>

          {/* Friendly hint + mascot peek — single mode only. Bulk uses
              the auto-scan indicator below the viewfinder instead. */}
          {!isBulk && (
            <div className="absolute bottom-4 left-0 right-0 flex justify-center pointer-events-none">
              <div className="bg-white/95 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-[#FACC15] flex items-center gap-2.5">
                <span className="font-semibold text-sm text-[#2D2A26]">
                  Show me your card!
                </span>
                <motion.div
                  animate={{ y: [0, -3, 0] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                  className="w-7 h-7 rounded-full overflow-hidden border-2 border-white bg-[#FACC15]/20"
                >
                  <Image
                    src="/pullist-mascot.png"
                    alt=""
                    width={28}
                    height={28}
                    className="object-cover"
                    unoptimized
                  />
                </motion.div>
              </div>
            </div>
          )}

          {/* Camera not-ready / error overlay */}
          {!cameraReady && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/70 text-center px-6">
              <p className="text-sm font-semibold text-[#2D2A26]">
                {cameraError ?? "Starting camera…"}
              </p>
              {cameraError && (
                <p className="mt-2 text-xs text-[#8A7E72]">
                  Use the gallery icon below to upload a photo instead.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Bulk mode panel — detection banner + running list. Replaces
            the single-mode "last scanned" pill below the viewfinder. */}
        {isBulk && (
          <BulkScanPanel
            detected={bulkDetected}
            identifying={bulkIdentifying}
            scanCount={bulkScanCount}
            drift={bulkDrift}
            stableTicks={bulkStableTicks}
            tickCount={bulkTickCount}
            list={bulkList}
            adding={bulkAdding}
            onAdd={onBulkAdd}
            onDismiss={onBulkDismiss}
            onClearList={onBulkClearList}
            onForceScan={onBulkForceScan}
          />
        )}

        {/* Last Scanned pill — single mode only. */}
        {!isBulk && lastScanned && (
          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            onClick={onLastScannedTap}
            className="w-full bg-white p-3 rounded-[1.5rem] border-2 border-[#FACC15] shadow-sm flex items-center gap-3 text-left"
          >
            <div className="w-10 h-14 bg-[#FFF3DE] rounded-lg overflow-hidden border border-[#FDE2C7] shrink-0">
              {lastScanned.thumbUrl && (
                <Image
                  src={lastScanned.thumbUrl}
                  alt=""
                  width={40}
                  height={56}
                  className="w-full h-full object-cover"
                  unoptimized
                />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-bold text-[#8A7E72] uppercase tracking-widest">
                Last Scanned
              </p>
              <p className="font-bold text-[#2D2A26] truncate">
                {lastScanned.name}
                {lastScanned.number && (
                  <span className="text-[#8A7E72] ml-1 font-mono text-xs">
                    #{lastScanned.number}
                  </span>
                )}
              </p>
              {lastScanned.priceUsd != null && (
                <p className="text-[#22C55E] font-bold text-sm">
                  {fmtPrice(lastScanned.priceUsd)}
                </p>
              )}
            </div>
            {pendingCount > 0 && (
              <div className="relative shrink-0 mr-1">
                <div className="w-12 h-14 rounded-xl bg-[#FFF3DE] border-2 border-dashed border-[#14B8A6] flex items-center justify-center">
                  <ImageIcon className="w-5 h-5 text-[#14B8A6]" />
                </div>
                <span className="absolute -top-1.5 -right-1.5 bg-[#14B8A6] text-white text-[10px] font-black w-5 h-5 rounded-full flex items-center justify-center border-2 border-white shadow-sm">
                  {pendingCount}
                </span>
              </div>
            )}
          </motion.button>
        )}
      </main>

      {/* Bottom controls */}
      <footer className="p-6 pb-[calc(2.5rem_+_env(safe-area-inset-bottom))] flex items-center justify-between relative z-10">
        <button
          type="button"
          onClick={openGalleryPicker}
          aria-label="Upload from gallery"
          className="w-14 h-14 rounded-full bg-[#14B8A6]/10 flex items-center justify-center border-2 border-[#14B8A6]/30 active:scale-95 transition"
        >
          <ImageIcon className="w-6 h-6 text-[#14B8A6]" />
        </button>
        {/*
          NO `capture` attr — the bug was that capture="environment"
          forces iOS/Android to open the camera UI again instead of
          letting the user pick from their photo library. Plain
          accept="image/*" gives the native picker (Photo Library /
          Take Photo / Choose File) the user expects.
        */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={onFilePicked}
          className="hidden"
        />

        {isBulk ? (
          // Bulk mode auto-scans on a timer, so there's no shutter.
          // Swap in a dimmer "scanning…" pulse in the same slot so the
          // footer keeps its three-column balance.
          <div
            aria-label="Auto scanning"
            className="relative w-20 h-20 rounded-full bg-white/70 border-[6px] border-white shadow-md flex items-center justify-center"
          >
            {cameraReady && (
              <div className="absolute inset-1 rounded-full bg-[#22C55E]/20 animate-ping" />
            )}
            <div className="w-3 h-3 rounded-full bg-[#22C55E] relative" />
          </div>
        ) : (
          <motion.button
            type="button"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.92 }}
            onClick={onShutter}
            disabled={!cameraReady}
            aria-label="Take photo"
            className="relative w-20 h-20 rounded-full bg-[#FACC15] border-[6px] border-white shadow-lg flex items-center justify-center disabled:opacity-50"
          >
            {cameraReady && (
              <div className="absolute inset-0 rounded-full bg-[#FACC15]/30 animate-ping" />
            )}
            <Sparkles className="w-7 h-7 text-white relative" />
          </motion.button>
        )}

        <button
          type="button"
          onClick={onFlipCamera}
          aria-label="Flip camera"
          className="w-14 h-14 rounded-full bg-white flex items-center justify-center border border-[#FDE2C7] shadow-sm text-[#8A7E72] active:scale-95 transition"
        >
          <RotateCw className="w-6 h-6" />
        </button>
      </footer>
      </div>
    </div>
  );
}
