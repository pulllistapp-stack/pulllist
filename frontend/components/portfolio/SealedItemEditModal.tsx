"use client";

/**
 * SealedItemEditModal — inline edit UI for a row in the sealed
 * portfolio. Mirrors the singles CollectionItemEditModal but stripped
 * to the fields sealed products actually carry:
 *   - qty
 *   - condition (sealed / opened / damaged — no NM/LP grading)
 *   - purchase price + date + source
 *   - notes
 * No variant, no grading (cards get graded, boxes don't).
 */

import { useEffect, useState } from "react";
import Image from "next/image";
import { Check, Loader2, Minus, Plus, Trash2, X } from "lucide-react";

import {
  deleteSealedOwnership,
  upsertSealedOwnership,
  type SealedCollectionEntry,
  type SealedCondition,
} from "@/lib/api";

type Props = {
  entry: SealedCollectionEntry;
  onClose: () => void;
  onSaved: () => void;
  onDeleted: () => void;
};

const CONDITIONS: { value: SealedCondition; label: string; hint: string }[] = [
  { value: "sealed", label: "Sealed", hint: "Factory sealed, unopened" },
  { value: "opened", label: "Opened", hint: "Box opened, contents intact" },
  { value: "damaged", label: "Damaged", hint: "Box or contents damaged" },
];

const ACQUISITION_TYPES = [
  { value: "purchase", label: "Bought" },
  { value: "trade", label: "Traded" },
  { value: "gift", label: "Gift" },
  { value: "other", label: "Other" },
] as const;

export function SealedItemEditModal({
  entry,
  onClose,
  onSaved,
  onDeleted,
}: Props) {
  const { item, product } = entry;
  const [qty, setQty] = useState(item.qty);
  const [condition, setCondition] = useState<SealedCondition>(item.condition);
  const [priceStr, setPriceStr] = useState(
    item.purchase_price_usd != null ? String(item.purchase_price_usd) : "",
  );
  const [acquiredAt, setAcquiredAt] = useState(item.acquired_at ?? "");
  const [acquisitionType, setAcquisitionType] = useState(
    item.acquisition_type ?? "",
  );
  const [notes, setNotes] = useState(item.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const priceNum = priceStr === "" ? null : Number(priceStr);
  const priceValid = priceStr === "" || (!Number.isNaN(priceNum) && priceNum! >= 0);

  const paidTotal =
    priceValid && priceNum != null ? priceNum * qty : null;
  const marketTotal =
    product.market_price_usd != null ? product.market_price_usd * qty : null;
  const roi =
    paidTotal != null && marketTotal != null ? marketTotal - paidTotal : null;

  async function onSave() {
    if (!priceValid) {
      setError("Purchase price must be a non-negative number");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await upsertSealedOwnership(product.id, {
        qty,
        condition,
        purchase_price_usd: priceNum,
        acquisition_type: acquisitionType || null,
        acquired_at: acquiredAt || null,
        notes: notes || null,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteSealedOwnership(product.id);
      onDeleted();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-2xl border border-border bg-bg-surface shadow-2xl max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 rounded-full p-1.5 text-text-tertiary hover:text-text-primary hover:bg-bg transition-colors"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="p-5 pb-3 flex items-start gap-3">
          {product.image_url && (
            <div className="relative h-16 w-12 shrink-0 overflow-hidden rounded-md bg-bg">
              <Image
                src={product.image_url}
                alt={product.name}
                fill
                sizes="48px"
                className="object-contain"
                unoptimized
              />
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              {product.set_id ?? "—"}
            </div>
            <h2 className="text-base font-bold text-text-primary truncate">
              {product.name}
            </h2>
            {product.market_price_usd != null && (
              <div className="text-xs text-text-secondary font-mono">
                Market ${product.market_price_usd.toFixed(2)}
              </div>
            )}
          </div>
        </div>

        <div className="px-5 pb-5 space-y-4">
          {/* Qty */}
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
              Quantity
            </label>
            <div className="inline-flex items-center gap-2 rounded-btn border border-border bg-bg p-1">
              <button
                type="button"
                onClick={() => setQty((q) => Math.max(1, q - 1))}
                className="rounded-btn p-1.5 text-text-secondary hover:text-text-primary hover:bg-bg-surface"
                aria-label="Decrement"
              >
                <Minus className="h-3 w-3" />
              </button>
              <span className="w-8 text-center font-mono font-bold">{qty}</span>
              <button
                type="button"
                onClick={() => setQty((q) => Math.min(999, q + 1))}
                className="rounded-btn p-1.5 text-text-secondary hover:text-text-primary hover:bg-bg-surface"
                aria-label="Increment"
              >
                <Plus className="h-3 w-3" />
              </button>
            </div>
          </div>

          {/* Condition */}
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
              Condition
            </label>
            <div className="flex flex-wrap gap-2">
              {CONDITIONS.map((c) => (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setCondition(c.value)}
                  title={c.hint}
                  className={
                    "rounded-full border px-3 py-1 text-xs font-semibold transition-colors " +
                    (condition === c.value
                      ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                      : "border-border bg-bg text-text-secondary hover:text-text-primary")
                  }
                >
                  {c.label}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[10px] text-text-tertiary/80">
              {CONDITIONS.find((c) => c.value === condition)?.hint}
            </p>
          </div>

          {/* Purchase price */}
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
              Purchase price ($ per unit)
            </label>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              value={priceStr}
              onChange={(e) => setPriceStr(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-sm focus:outline-none focus:border-accent-yellow"
            />
            {!priceValid && (
              <p className="mt-1 text-[11px] text-red-400">
                Must be a non-negative number.
              </p>
            )}
            {(paidTotal != null || marketTotal != null) && (
              <div className="mt-2 rounded-lg bg-bg/60 px-3 py-2 text-xs font-mono text-text-secondary">
                {paidTotal != null && (
                  <div>
                    Paid total: ${paidTotal.toFixed(2)}
                    {qty > 1 && ` (${qty} × $${priceNum!.toFixed(2)})`}
                  </div>
                )}
                {marketTotal != null && (
                  <div>Market total: ${marketTotal.toFixed(2)}</div>
                )}
                {roi != null && (
                  <div
                    className={
                      roi > 0
                        ? "text-accent-green font-semibold"
                        : roi < 0
                        ? "text-red-400 font-semibold"
                        : ""
                    }
                  >
                    P/L: {roi > 0 ? "+" : ""}${roi.toFixed(2)}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Acquisition */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
                Acquired date
              </label>
              <input
                type="date"
                value={acquiredAt}
                onChange={(e) => setAcquiredAt(e.target.value)}
                className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-sm focus:outline-none focus:border-accent-yellow"
              />
            </div>
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
                Source
              </label>
              <select
                value={acquisitionType}
                onChange={(e) => setAcquisitionType(e.target.value)}
                className="w-full rounded-btn border border-border bg-bg px-3 py-2 font-mono text-sm focus:outline-none focus:border-accent-yellow"
              >
                <option value="">—</option>
                {ACQUISITION_TYPES.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">
              Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              maxLength={500}
              placeholder="Store, batch, condition notes…"
              className="w-full rounded-btn border border-border bg-bg px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow resize-none"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2">
            {!confirmDelete ? (
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="inline-flex items-center gap-1.5 rounded-btn border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/15 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" /> Remove
              </button>
            ) : (
              <div className="inline-flex items-center gap-1.5 rounded-btn border border-red-500/60 bg-red-500/20 px-2 py-1 text-xs font-semibold text-red-300">
                <span>Really remove?</span>
                <button
                  type="button"
                  onClick={onDelete}
                  disabled={deleting}
                  className="rounded-btn bg-red-500 px-2 py-1 text-white hover:bg-red-600 disabled:opacity-50"
                >
                  {deleting ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    "Yes"
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="rounded-btn px-2 py-1 text-text-secondary hover:text-text-primary"
                >
                  No
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={onSave}
              disabled={saving || !priceValid}
              className="ml-auto inline-flex items-center gap-1.5 rounded-btn bg-accent-yellow px-4 py-2 text-sm font-bold text-gray-900 hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {saving ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Check className="h-3.5 w-3.5" />
              )}
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
