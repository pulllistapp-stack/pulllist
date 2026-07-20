"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Minus, Plus, X } from "lucide-react";
import Image from "next/image";

import { VariantChip } from "@/components/VariantChip";
import { GradedTierPreview } from "@/components/portfolio/GradedTierPreview";
import {
  createCollectionItem,
  type AcquisitionType,
  type CardVariant,
} from "@/lib/auth";
import { GRADE_SERVICES } from "@/lib/gradedTier";
import { availableVariants, VARIANT_LABELS } from "@/lib/variant";
import { cn } from "@/lib/utils";

type CardLike = {
  id: string;
  name: string;
  number?: string | null;
  image_small?: string | null;
  tcgplayer_prices?: unknown;
};

type Props = {
  card: CardLike;
  /** Variant the user was viewing on the detail page — pre-selected. */
  initialVariant?: CardVariant;
  onClose: () => void;
  onAdded: () => void;
};

const CONDITIONS: { value: "NM" | "LP" | "MP" | "HP" | "DMG"; label: string }[] = [
  { value: "NM", label: "NM" },
  { value: "LP", label: "LP" },
  { value: "MP", label: "MP" },
  { value: "HP", label: "HP" },
  { value: "DMG", label: "DMG" },
];

const GRADES = [
  "10",
  "9.5",
  "9",
  "8.5",
  "8",
  "7",
  "6",
  "5",
  "4",
  "3",
  "2",
  "1",
];

const SOURCES: { value: AcquisitionType; label: string; hint: string }[] = [
  { value: "pull", label: "Pulled", hint: "Out of a pack" },
  { value: "purchase", label: "Bought", hint: "Bought it solo" },
  { value: "trade", label: "Traded", hint: "Swapped for it" },
  { value: "gift", label: "Gift", hint: "Someone gave it" },
  { value: "other", label: "Other", hint: "" },
];

/**
 * Modal that opens when a logged-in user clicks "+ I have this" on a card
 * they don't already own. Captures the full per-row context — variant,
 * condition, grade, qty, purchase price, source, notes — so the Portfolio
 * has real provenance instead of the old 1-click toggle that just dropped a
 * blank row at NM/normal.
 */
export function CardAddModal({
  card,
  initialVariant = "normal",
  onClose,
  onAdded,
}: Props) {
  const variants = useMemo(
    () => availableVariants(card.tcgplayer_prices),
    [card.tcgplayer_prices],
  );
  const showVariants = variants.length >= 2;

  const [variant, setVariant] = useState<CardVariant>(
    showVariants && variants.includes(initialVariant)
      ? initialVariant
      : (variants[0] ?? "normal"),
  );
  const [condition, setCondition] = useState<"NM" | "LP" | "MP" | "HP" | "DMG">(
    "NM",
  );
  const [isGraded, setIsGraded] = useState(false);
  const [gradeService, setGradeService] = useState("PSA");
  const [gradeValue, setGradeValue] = useState("10");
  const [qty, setQty] = useState(1);
  const [acquiredAt, setAcquiredAt] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  });
  const [purchasePrice, setPurchasePrice] = useState("");
  const [source, setSource] = useState<AcquisitionType | "">("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const priceNum = purchasePrice ? parseFloat(purchasePrice) : null;
  const priceValid =
    purchasePrice === "" ||
    (priceNum !== null && !Number.isNaN(priceNum) && priceNum >= 0);

  const onSubmit = async () => {
    if (!priceValid) {
      setErr("Purchase price must be a non-negative number");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await createCollectionItem({
        card_id: card.id,
        qty,
        variant,
        condition,
        is_graded: isGraded,
        grade: isGraded ? `${gradeService} ${gradeValue}` : null,
        acquired_at: acquiredAt || null,
        notes: notes.trim() || null,
        purchase_price_usd: priceNum,
        acquisition_type: source || null,
      });
      onAdded();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Add failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg max-h-[90vh] rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/20 overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start gap-3 p-5 border-b border-border">
          {card.image_small && (
            <div className="shrink-0 w-12 h-16 rounded-md overflow-hidden bg-bg-elevated">
              <Image
                src={card.image_small}
                alt=""
                width={48}
                height={64}
                className="object-cover w-full h-full"
                unoptimized
              />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-mono uppercase tracking-wider text-accent-green">
              Add to collection
            </p>
            <h2 className="text-lg font-bold text-text-primary truncate">
              {card.name}
            </h2>
            {card.number && (
              <p className="text-xs text-text-tertiary font-mono mt-0.5">
                #{card.number}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-full text-text-tertiary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="p-5 space-y-5 overflow-y-auto">
          {showVariants && (
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
                Variant
              </label>
              <div className="flex flex-wrap gap-2">
                {variants.map((v) => (
                  <button
                    key={v}
                    onClick={() => setVariant(v)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold border transition-colors",
                      variant === v
                        ? "bg-accent-yellow text-gray-900 border-accent-yellow"
                        : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40",
                    )}
                  >
                    {variant === v && <Check className="h-3 w-3" />}
                    {VARIANT_LABELS[v]}
                    {v !== "normal" && variant !== v && (
                      <VariantChip variant={v} />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Condition */}
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
              Condition
            </label>
            <div className="grid grid-cols-5 gap-1.5">
              {CONDITIONS.map((c) => (
                <button
                  key={c.value}
                  onClick={() => setCondition(c.value)}
                  className={cn(
                    "rounded-btn py-2 text-xs font-bold font-mono border transition-colors",
                    condition === c.value
                      ? "bg-accent-yellow/15 border-accent-yellow/60 text-accent-yellow"
                      : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40",
                  )}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Graded toggle */}
          <div>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isGraded}
                onChange={(e) => setIsGraded(e.target.checked)}
                className="h-4 w-4 rounded accent-accent-yellow"
              />
              <span className="text-sm font-semibold text-text-primary">
                Graded
              </span>
              <span className="text-xs text-text-tertiary">
                PSA / BGS / CGC slab
              </span>
            </label>
            {isGraded && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-1">
                    Service
                  </label>
                  <select
                    value={gradeService}
                    onChange={(e) => setGradeService(e.target.value)}
                    className="w-full rounded-btn bg-bg border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent-yellow/60 transition-colors"
                  >
                    {GRADE_SERVICES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-1">
                    Grade
                  </label>
                  <select
                    value={gradeValue}
                    onChange={(e) => setGradeValue(e.target.value)}
                    className="w-full rounded-btn bg-bg border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent-yellow/60 transition-colors"
                  >
                    {GRADES.map((g) => (
                      <option key={g} value={g}>
                        {g}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
            <GradedTierPreview
              cardId={card.id}
              isGraded={isGraded}
              service={gradeService}
              value={gradeValue}
            />
          </div>

          {/* Quantity */}
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
              Quantity
            </label>
            <div className="inline-flex items-center gap-2 rounded-full bg-bg border border-border p-1">
              <button
                onClick={() => setQty((q) => Math.max(1, q - 1))}
                disabled={qty <= 1}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full hover:bg-bg-elevated transition-colors disabled:opacity-30"
                aria-label="Decrease quantity"
              >
                <Minus className="h-3.5 w-3.5" />
              </button>
              <span className="w-10 text-center text-sm font-bold font-mono tabular-nums">
                {qty}
              </span>
              <button
                onClick={() => setQty((q) => Math.min(999, q + 1))}
                disabled={qty >= 999}
                className="inline-flex h-8 w-8 items-center justify-center rounded-full hover:bg-bg-elevated transition-colors disabled:opacity-30"
                aria-label="Increase quantity"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Acquired + Purchase price (two-col) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="acquired-at"
                className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
              >
                Acquired
              </label>
              <input
                id="acquired-at"
                type="date"
                value={acquiredAt}
                onChange={(e) => setAcquiredAt(e.target.value)}
                className="w-full rounded-btn bg-bg border border-border px-3 py-2 text-sm font-mono focus:outline-none focus:border-accent-yellow/60 transition-colors"
              />
            </div>
            <div>
              <label
                htmlFor="purchase-price"
                className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
              >
                Paid (USD)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm font-mono">
                  $
                </span>
                <input
                  id="purchase-price"
                  type="number"
                  step="0.01"
                  min="0"
                  value={purchasePrice}
                  onChange={(e) => setPurchasePrice(e.target.value)}
                  placeholder="optional"
                  className="w-full rounded-btn bg-bg border border-border pl-7 pr-3 py-2 text-sm font-mono focus:outline-none focus:border-accent-yellow/60 transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Source */}
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
              Source <span className="lowercase opacity-70">(optional)</span>
            </label>
            <div className="grid grid-cols-5 gap-1.5">
              {SOURCES.map((s) => (
                <button
                  key={s.value}
                  onClick={() =>
                    setSource((cur) => (cur === s.value ? "" : s.value))
                  }
                  className={cn(
                    "rounded-btn py-2 text-xs font-bold border transition-colors",
                    source === s.value
                      ? "bg-accent-green/15 border-accent-green/60 text-accent-green"
                      : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-green/40",
                  )}
                  title={s.hint}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label
              htmlFor="add-notes"
              className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
            >
              Notes <span className="lowercase opacity-70">(optional)</span>
            </label>
            <textarea
              id="add-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              maxLength={500}
              placeholder="Pulled from Surging Sparks ETB · trade w/ Sam"
              className="w-full rounded-2xl bg-bg border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/60 focus:ring-2 focus:ring-accent-yellow/15 transition-colors resize-none"
            />
          </div>

          {err && (
            <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
              {err}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-5 border-t border-border bg-bg/40">
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            disabled={saving || !priceValid}
            className="inline-flex items-center gap-2 rounded-full bg-accent-green text-white font-bold px-5 py-2 text-sm hover:brightness-110 shadow-md shadow-accent-green/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Add to collection
          </button>
        </div>
      </div>
    </div>
  );
}
