"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { Check, Loader2, Plus, X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Bulk-mode UI strip: detection banner (when the pHash matcher finds
 * a card in the viewfinder) plus a running summary of what the user has
 * added this session. Sits below the ScanCamera viewfinder and mirrors
 * the same warm cream / yellow / teal palette.
 *
 * Presentational only — parent owns the pHash catalog, capture loop,
 * and mutation calls. This panel only fires the callbacks it's given.
 */

export type BulkDetected = {
  cardId: string;
  name: string;
  number: string | null;
  setName: string | null;
  imageUrl: string | null;
  priceUsd: number | null;
  distance: number;
};

export type BulkListItem = {
  cardId: string;
  name: string;
  imageUrl: string | null;
  priceUsd: number | null;
  addedAt: number;
};

type Props = {
  detected: BulkDetected | null;
  identifying: boolean;
  scanCount: number;
  drift: number | null;
  stableTicks: number;
  list: BulkListItem[];
  adding: boolean;
  onAdd: () => void;
  onDismiss: () => void;
  onClearList: () => void;
  onForceScan: () => void;
};

function fmtPrice(v: number | null): string {
  if (v == null || v <= 0) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

export function BulkScanPanel({
  detected,
  identifying,
  scanCount,
  drift,
  stableTicks,
  list,
  adding,
  onAdd,
  onDismiss,
  onClearList,
  onForceScan,
}: Props) {
  const total = list.reduce((s, it) => s + (it.priceUsd ?? 0), 0);

  return (
    <div className="w-full flex flex-col gap-3">

      {/* Detection banner — the star of the show. */}
      {detected && (
        <motion.div
          key={detected.cardId}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[1.5rem] border-2 border-[#FACC15] bg-white p-3 shadow-lg flex items-center gap-3"
        >
          <div className="w-14 h-20 rounded-xl overflow-hidden bg-[#FFF3DE] shrink-0 border border-[#FDE2C7]">
            {detected.imageUrl && (
              <Image
                src={detected.imageUrl}
                alt=""
                width={56}
                height={80}
                className="w-full h-full object-cover"
                unoptimized
              />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-black uppercase text-[#14B8A6] tracking-widest">
              Detected
            </p>
            <p className="font-bold text-[#2D2A26] truncate">
              {detected.name}
              {detected.number && (
                <span className="text-[#8A7E72] ml-1 font-mono text-xs">
                  #{detected.number}
                </span>
              )}
            </p>
            <p className="mt-0.5 text-lg font-black text-[#22C55E]">
              {fmtPrice(detected.priceUsd)}
            </p>
          </div>
          <div className="flex flex-col gap-1.5 shrink-0">
            <button
              type="button"
              onClick={onAdd}
              disabled={adding}
              className="inline-flex items-center gap-1 rounded-full bg-[#22C55E] text-white font-black px-3 py-1.5 text-xs shadow-sm disabled:opacity-60"
            >
              {adding ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Plus className="h-3 w-3" />
              )}
              Add
            </button>
            <button
              type="button"
              onClick={onDismiss}
              disabled={adding}
              className="inline-flex items-center gap-1 rounded-full border border-[#FDE2C7] text-[#8A7E72] font-bold px-2.5 py-1 text-[10px]"
            >
              <X className="h-3 w-3" />
              Skip
            </button>
          </div>
        </motion.div>
      )}

      {/* Idle / status hint. Two visual states:
          - identifying: yellow spinner, "reading card…"
          - idle: green pulse, "hold a card"
          Diagnostic line below shows frame drift + stability tick
          count so we can watch the trigger from LO's phone. A
          manual "Scan now" button forces a vision call regardless
          of stability — isolates the vision-call path from the
          stability detector when debugging. */}
      {!detected && (
        <div className="rounded-xl bg-white/90 border border-[#FDE2C7] px-3 py-2 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {identifying ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-[#FACC15] shrink-0" />
                  <span className="text-xs font-semibold text-[#2D2A26]">
                    Reading card…
                  </span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 rounded-full bg-[#22C55E] animate-pulse shrink-0" />
                  <span className="text-xs font-semibold text-[#8A7E72]">
                    Hold a card steady in the frame
                  </span>
                </>
              )}
            </div>
            {scanCount > 0 && (
              <span className="text-[10px] font-mono text-[#8A7E72] shrink-0">
                {scanCount} scan{scanCount === 1 ? "" : "s"}
              </span>
            )}
          </div>
          <div className="mt-1.5 flex items-center justify-between gap-2 pl-4">
            <span className="text-[10px] font-mono text-[#B8A99A]">
              drift{" "}
              {drift == null ? "—" : `${drift}/14`} · steady {stableTicks}/2
            </span>
            <button
              type="button"
              onClick={onForceScan}
              disabled={identifying}
              className="rounded-full bg-[#14B8A6] text-white text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 shadow-sm disabled:opacity-50"
            >
              Scan now
            </button>
          </div>
        </div>
      )}

      {/* Running list summary. Shows total + strip of thumbnails so LO can
          see what's been captured this session. Clear button resets. */}
      {list.length > 0 && (
        <div className="rounded-2xl bg-white border border-[#FDE2C7] shadow-sm p-3">
          <div className="flex items-baseline justify-between mb-2">
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
                Added this session
              </p>
              <p className="text-sm font-bold text-[#2D2A26]">
                {list.length} card{list.length !== 1 ? "s" : ""}{" "}
                <span className="text-[#22C55E]">·  {fmtPrice(total)}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={onClearList}
              className={cn(
                "rounded-full border border-[#FDE2C7] text-[#8A7E72] text-[10px] font-bold uppercase tracking-wider px-2.5 py-1",
                "hover:text-[#2D2A26] hover:bg-[#FFF3DE] transition-colors",
              )}
            >
              Clear
            </button>
          </div>
          {/* Horizontal thumbnail strip — most recent left. */}
          <div className="flex gap-1.5 overflow-x-auto -mx-1 px-1 pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {list.map((it) => (
              <div
                key={`${it.cardId}-${it.addedAt}`}
                className="relative shrink-0 w-10 h-14 rounded-md overflow-hidden bg-[#FFF3DE] border border-[#FDE2C7]"
                title={`${it.name} · ${fmtPrice(it.priceUsd)}`}
              >
                {it.imageUrl && (
                  <Image
                    src={it.imageUrl}
                    alt=""
                    width={40}
                    height={56}
                    className="w-full h-full object-cover"
                    unoptimized
                  />
                )}
                <div className="absolute bottom-0 right-0 bg-[#22C55E] text-white rounded-tl-md px-0.5 py-px">
                  <Check className="h-2.5 w-2.5" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
