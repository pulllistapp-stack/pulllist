"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import {
  ChevronLeft,
  Loader2,
  MessageCircle,
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

type Grader = "PSA" | "BGS" | "CGC" | "Raw";
type Condition = "NM" | "LP" | "MP" | "HP" | "DMG";

type Props = {
  photoSrc: string;
  matched: MatchedCardForConfirm | null;
  /** Whether a successful add has fired — drives the "Got one! ✨" peek */
  addedSuccess: boolean;
  submitting: boolean;
  onAdd: (params: { grader: Grader; condition: Condition; qty: number }) => void;
  onDiscard: () => void;
  onSearchManually: () => void;
  onBack: () => void;
};

const GRADERS: Grader[] = ["PSA", "BGS", "CGC", "Raw"];
const CONDITIONS: Condition[] = ["NM", "LP", "MP", "HP", "DMG"];

function fmtPrice(v: number | null): string {
  if (v == null || v <= 0) return "—";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

/** Screen 2 — confirm + edit + add. Presentation; parent owns scan/add APIs. */
export function ScanConfirm({
  photoSrc,
  matched,
  addedSuccess,
  submitting,
  onAdd,
  onDiscard,
  onSearchManually,
  onBack,
}: Props) {
  const [grader, setGrader] = useState<Grader>("Raw");
  const [condition, setCondition] = useState<Condition>("NM");

  const submit = () => {
    if (submitting || !matched) return;
    onAdd({ grader, condition, qty: 1 });
  };

  return (
    <div className="min-h-[100dvh] bg-[#FFF8E7] text-[#2D2A26] flex flex-col max-w-md mx-auto relative overflow-hidden border-x border-[#FDE2C7]">
      {/* Header */}
      <header className="p-5 flex items-center justify-between relative z-10">
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

      <main className="flex-1 px-5 flex flex-col gap-5 relative z-10">
        {/* Side-by-side comparison */}
        <div className="flex items-center justify-center gap-3 py-2">
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-[10px] font-black uppercase text-[#8A7E72] tracking-[0.2em]">
              Your photo
            </span>
            <div className="w-28 aspect-[3/4] rounded-2xl bg-white border border-[#FDE2C7] overflow-hidden -rotate-2 shadow-md">
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
              Matched
            </span>
            <div className="w-32 aspect-[3/4] rounded-2xl bg-white border-[3px] border-[#FACC15] overflow-hidden rotate-2 shadow-xl relative">
              {matched?.imageUrl ? (
                <Image
                  src={matched.imageUrl}
                  alt={matched.name}
                  width={160}
                  height={224}
                  className="w-full h-full object-cover"
                  unoptimized
                />
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

        {/* Card info + grader/condition */}
        <div className="bg-white p-5 rounded-[2rem] border border-[#FDE2C7] shadow-sm space-y-4">
          {matched ? (
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

              <SegmentRow
                label="Grader"
                values={GRADERS}
                selected={grader}
                onSelect={setGrader}
              />
              <SegmentRow
                label="Condition"
                values={CONDITIONS}
                selected={condition}
                onSelect={setCondition}
                hollowSelected
              />
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
      <footer className="p-5 pt-3 pb-8 flex gap-3 items-center relative z-10">
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
          whileHover={{ scale: matched ? 1.02 : 1 }}
          whileTap={{ scale: matched ? 0.97 : 1 }}
          onClick={submit}
          disabled={!matched || submitting}
          className="flex-1 h-14 bg-[#FACC15] rounded-full shadow-lg border-b-4 border-[#EAB308] flex items-center justify-center gap-2 font-black text-base text-[#2D2A26] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-b-2"
        >
          {submitting ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <>
              <Plus className="w-5 h-5" />
              Add to collection
            </>
          )}
        </motion.button>
      </footer>

      {/* Success peek — appears for ~2s after add */}
      {addedSuccess && (
        <motion.div
          initial={{ opacity: 0, scale: 0.5, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0 }}
          className="pointer-events-none fixed inset-x-0 top-24 z-50 flex justify-center"
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

function SegmentRow<T extends string>({
  label,
  values,
  selected,
  onSelect,
  hollowSelected = false,
}: {
  label: string;
  values: readonly T[];
  selected: T;
  onSelect: (v: T) => void;
  hollowSelected?: boolean;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-black uppercase tracking-widest text-[#8A7E72]">
        {label}
      </label>
      <div className="flex p-1 bg-[#FFF3DE] rounded-full border border-[#FDE2C7]">
        {values.map((v) => {
          const active = v === selected;
          return (
            <button
              key={v}
              type="button"
              onClick={() => onSelect(v)}
              className={cn(
                "flex-1 py-2 rounded-full text-xs font-black transition-all min-w-0",
                active
                  ? hollowSelected
                    ? "border-2 border-[#FACC15] text-[#2D2A26] bg-white shadow-sm"
                    : "bg-[#FACC15] text-[#2D2A26] shadow-sm"
                  : "text-[#8A7E72]",
              )}
            >
              {v}
            </button>
          );
        })}
      </div>
    </div>
  );
}
