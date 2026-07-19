"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import {
  ChevronLeft,
  Loader2,
  MessageCircle,
  Minus,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

export type MatchedCardForConfirm = {
  cardId: string;
  name: string;
  number: string | null;
  setName: string | null;
  imageUrl: string | null;
  marketPriceUsd: number | null;
  language?: string | null;
};

export type ScanVariant = "normal" | "reverseHolofoil";
export type ScanGrader = "Raw" | "PSA" | "BGS" | "CGC" | "TAG" | "AGS";
export type ScanCondition = "NM" | "LP" | "MP" | "HP" | "DMG";

type Props = {
  photoSrc: string;
  matched: MatchedCardForConfirm | null;
  /** True while the backend scan call is in flight — distinguishes
   *  "still working" from "tried and failed". Both states currently
   *  have matched=null. */
  scanning: boolean;
  /** Whether a successful add has fired — drives the "Got one! ✨" peek */
  addedSuccess: boolean;
  submitting: boolean;
  onAdd: (params: {
    variant: ScanVariant;
    grader: ScanGrader;
    condition: ScanCondition;
    qty: number;
    pricePaidUsd: number | null;
  }) => void;
  onDiscard: () => void;
  onSearchManually: () => void;
  onBack: () => void;
};

const GRADERS: ScanGrader[] = ["Raw", "PSA", "BGS", "CGC", "TAG", "AGS"];
const CONDITIONS: { value: ScanCondition; full: string }[] = [
  { value: "NM", full: "Nearly Mint (NM)" },
  { value: "LP", full: "Lightly Played (LP)" },
  { value: "MP", full: "Moderately Played (MP)" },
  { value: "HP", full: "Heavily Played (HP)" },
  { value: "DMG", full: "Damaged (D)" },
];

function fmtPrice(v: number | null): string {
  if (v == null || v <= 0) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

/** Screen 2 — confirm + edit + add. Variant / grader / condition /
 *  price-paid / quantity all editable inline so the user never has
 *  to leave the scan flow. */
export function ScanConfirm({
  photoSrc,
  matched,
  scanning,
  addedSuccess,
  submitting,
  onAdd,
  onDiscard,
  onSearchManually,
  onBack,
}: Props) {
  const [variant, setVariant] = useState<ScanVariant>("normal");
  const [grader, setGrader] = useState<ScanGrader>("Raw");
  const [condition, setCondition] = useState<ScanCondition>("NM");
  const [qty, setQty] = useState<number>(1);
  const [priceStr, setPriceStr] = useState<string>("");

  const priceNum = priceStr ? Number(priceStr) : NaN;
  const priceValid =
    priceStr === "" || (!Number.isNaN(priceNum) && priceNum >= 0 && priceNum <= 999_999);

  const submit = () => {
    if (submitting || !matched || !priceValid) return;
    onAdd({
      variant,
      grader,
      condition,
      qty,
      pricePaidUsd: priceStr === "" ? null : Number(priceStr),
    });
  };

  return (
    <div className="min-h-[100dvh] bg-[#FFF8E7] text-[#2D2A26] flex flex-col max-w-md mx-auto relative overflow-hidden border-x border-[#FDE2C7]">
      {/* Header */}
      <header className="p-5 pt-[calc(1.25rem_+_env(safe-area-inset-top))] flex items-center justify-between relative z-10">
        <button
          type="button"
          onClick={onBack}
          aria-label="Back"
          className="w-10 h-10 rounded-full bg-white shadow-sm flex items-center justify-center border border-[#FDE2C7] active:scale-95 transition"
        >
          <ChevronLeft className="w-6 h-6 text-[#2D2A26]" />
        </button>
        <div className="bg-white px-4 py-1.5 rounded-full shadow-sm border border-[#FDE2C7] font-extrabold tracking-tight text-[#14B8A6] flex items-center gap-1.5">
          Confirm Match <span className="text-[#FACC15]">★</span>
        </div>
        <div className="w-10" />
      </header>

      <main className="flex-1 px-5 pb-3 flex flex-col gap-4 relative z-10 overflow-y-auto">
        {/* Side-by-side comparison */}
        <div className="flex items-center justify-center gap-3 py-1">
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-[10px] font-black uppercase text-[#8A7E72] tracking-[0.2em]">
              Your photo
            </span>
            <div className="w-24 aspect-[3/4] rounded-2xl bg-white border border-[#FDE2C7] overflow-hidden -rotate-2 shadow-md">
              {photoSrc && (
                <Image
                  src={photoSrc}
                  alt="Your scan"
                  width={140}
                  height={196}
                  className="w-full h-full object-cover"
                  unoptimized
                />
              )}
            </div>
          </div>

          <Star className="w-5 h-5 text-[#FACC15] fill-[#FACC15] mt-2 animate-pulse" />

          <div className="flex flex-col items-center gap-1.5">
            <span className="text-[10px] font-black uppercase text-[#14B8A6] tracking-[0.2em]">
              {scanning ? "Scanning…" : "Matched"}
            </span>
            <div className="w-28 aspect-[3/4] rounded-2xl bg-white border-[3px] border-[#FACC15] overflow-hidden rotate-2 shadow-xl relative">
              {matched?.imageUrl ? (
                <Image
                  src={matched.imageUrl}
                  alt={matched.name}
                  width={160}
                  height={224}
                  className="w-full h-full object-cover"
                  unoptimized
                />
              ) : scanning ? (
                <div className="w-full h-full bg-[#FFF3DE] flex flex-col items-center justify-center gap-1.5 px-2 text-center">
                  <motion.div
                    animate={{ scale: [1, 1.1, 1], rotate: [0, 5, -5, 0] }}
                    transition={{ duration: 1.4, repeat: Infinity }}
                  >
                    <Image
                      src="/pullist-mascot.png"
                      alt=""
                      width={40}
                      height={40}
                      className="rounded-full"
                      unoptimized
                    />
                  </motion.div>
                  <p className="text-[10px] font-black text-[#14B8A6] uppercase tracking-wider">
                    Reading
                    <motion.span
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1.2, repeat: Infinity }}
                    >
                      …
                    </motion.span>
                  </p>
                </div>
              ) : (
                <div className="w-full h-full bg-[#FFF3DE]" />
              )}
              <Star className="absolute top-1.5 right-1.5 w-4 h-4 text-[#FACC15] fill-[#FACC15]" />
            </div>
          </div>
        </div>

        {/* Manual search fallback */}
        <button
          type="button"
          onClick={onSearchManually}
          className="mx-auto inline-flex items-center gap-2 px-4 py-2 bg-[#14B8A6]/10 rounded-full border border-[#14B8A6]/30 text-[#14B8A6] font-bold text-sm hover:bg-[#14B8A6]/20 transition-colors"
        >
          <MessageCircle className="w-4 h-4" />
          Wrong match? Search manually
        </button>

        {/* Card info + form */}
        <div className="bg-white p-5 rounded-[2rem] border border-[#FDE2C7] shadow-sm space-y-4">
          {scanning ? (
            <div className="py-4 flex flex-col items-center gap-3 text-center">
              <Loader2 className="w-6 h-6 animate-spin text-[#FACC15]" />
              <p className="text-sm font-bold text-[#2D2A26]">
                Scanning your card…
              </p>
              <p className="text-xs text-[#8A7E72]">
                Reading the card name + number with vision AI.
                Takes a couple seconds.
              </p>
            </div>
          ) : matched ? (
            <>
              <div className="flex justify-between items-start gap-3">
                <div className="min-w-0 flex-1">
                  <h2 className="text-xl font-black truncate">{matched.name}</h2>
                  <p className="font-mono text-xs text-[#8A7E72] truncate mt-0.5">
                    {[
                      matched.number ? `#${matched.number}` : null,
                      matched.language ?? "EN",
                      matched.setName,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-xl font-black text-[#22C55E]">
                    {fmtPrice(matched.marketPriceUsd)}
                  </p>
                  <p className="text-[9px] text-[#8A7E72] font-bold uppercase tracking-wider">
                    Market
                  </p>
                </div>
              </div>

              {/* Variant */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
                  Variant
                </label>
                <div className="flex gap-2">
                  <PillButton
                    active={variant === "normal"}
                    onClick={() => setVariant("normal")}
                  >
                    Normal
                  </PillButton>
                  <PillButton
                    active={variant === "reverseHolofoil"}
                    onClick={() => setVariant("reverseHolofoil")}
                  >
                    Reverse Holofoil
                  </PillButton>
                </div>
              </div>

              {/* Grader — 6 options, wrap on narrow */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
                  Grader
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {GRADERS.map((g) => (
                    <PillButton
                      key={g}
                      active={grader === g}
                      onClick={() => setGrader(g)}
                      size="sm"
                    >
                      {g}
                    </PillButton>
                  ))}
                </div>
              </div>

              {/* Condition — full names, wrap freely */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
                  Condition
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {CONDITIONS.map((c) => (
                    <PillButton
                      key={c.value}
                      active={condition === c.value}
                      onClick={() => setCondition(c.value)}
                      size="sm"
                      hollowActive
                    >
                      {c.full}
                    </PillButton>
                  ))}
                </div>
              </div>

              {/* Price paid */}
              <div className="space-y-1.5">
                <label
                  htmlFor="scan-price"
                  className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]"
                >
                  Price paid, $
                </label>
                <input
                  id="scan-price"
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  min="0"
                  max="999999"
                  value={priceStr}
                  onChange={(e) => setPriceStr(e.target.value)}
                  placeholder="ex. 12.99"
                  className={cn(
                    "w-full rounded-2xl bg-[#FFF3DE] border px-4 py-2.5 text-sm focus:outline-none focus:ring-2 transition-colors",
                    priceValid
                      ? "border-[#FDE2C7] focus:border-[#FACC15] focus:ring-[#FACC15]/30"
                      : "border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]/30",
                  )}
                />
                {!priceValid && (
                  <p className="text-[10px] text-[#EF4444] font-bold">
                    Price must be 0 – 999,999
                  </p>
                )}
              </div>

              {/* Quantity */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
                  Quantity
                </label>
                <div className="flex items-center justify-between bg-[#FFF3DE] border border-[#FDE2C7] rounded-2xl p-1">
                  <button
                    type="button"
                    onClick={() => setQty((q) => Math.max(1, q - 1))}
                    disabled={qty <= 1}
                    aria-label="Decrease quantity"
                    className="w-12 h-10 inline-flex items-center justify-center rounded-xl hover:bg-white disabled:opacity-30 transition"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="text-lg font-black tabular-nums">{qty}</span>
                  <button
                    type="button"
                    onClick={() => setQty((q) => Math.min(999, q + 1))}
                    disabled={qty >= 999}
                    aria-label="Increase quantity"
                    className="w-12 h-10 inline-flex items-center justify-center rounded-xl hover:bg-white disabled:opacity-30 transition"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-[#8A7E72]">
              We couldn&apos;t identify this card from the photo. Try
              re-taking it on a flat surface, or use the manual search
              above.
            </p>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="p-5 pt-3 pb-[calc(2rem_+_env(safe-area-inset-bottom))] flex gap-3 items-center relative z-10 bg-[#FFF8E7] border-t border-[#FDE2C7]/40">
        <button
          type="button"
          onClick={onDiscard}
          aria-label="Discard"
          className="w-14 h-14 rounded-2xl bg-red-50 border-2 border-red-100 flex items-center justify-center text-[#EF4444] active:scale-95 transition shrink-0"
        >
          <Trash2 className="w-5 h-5" />
        </button>

        <motion.button
          type="button"
          whileHover={{ scale: matched && priceValid ? 1.02 : 1 }}
          whileTap={{ scale: matched && priceValid ? 0.97 : 1 }}
          onClick={submit}
          disabled={!matched || submitting || !priceValid}
          className="flex-1 h-14 bg-[#FACC15] rounded-full shadow-lg border-b-4 border-[#EAB308] flex items-center justify-center gap-2 font-black text-base text-[#2D2A26] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-b-2"
        >
          {submitting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              <Plus className="w-5 h-5" />
              Collect this card
            </>
          )}
        </motion.button>
      </footer>

      {/* Success peek */}
      {addedSuccess && (
        <motion.div
          initial={{ opacity: 0, scale: 0.5, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="pointer-events-none fixed inset-x-0 top-20 z-50 flex justify-center px-4"
        >
          <div className="bg-white px-5 py-3 rounded-2xl shadow-xl border-2 border-[#14B8A6] flex items-center gap-3">
            <Image
              src="/pullist-mascot.png"
              alt=""
              width={36}
              height={36}
              className="rounded-full"
              unoptimized
            />
            <span className="font-black text-sm text-[#14B8A6]">
              Got one! ✨
            </span>
          </div>
        </motion.div>
      )}
    </div>
  );
}

function PillButton({
  active,
  onClick,
  children,
  size = "md",
  hollowActive = false,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  size?: "sm" | "md";
  hollowActive?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full font-black transition-all border",
        size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
        active
          ? hollowActive
            ? "border-[#FACC15] border-2 bg-white text-[#2D2A26] shadow-sm"
            : "bg-[#FACC15] border-[#FACC15] text-[#2D2A26] shadow-sm"
          : "border-[#FDE2C7] bg-[#FFF3DE] text-[#8A7E72] hover:text-[#2D2A26] hover:bg-white",
      )}
    >
      {children}
    </button>
  );
}
