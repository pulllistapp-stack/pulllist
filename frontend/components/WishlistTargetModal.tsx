"use client";

import { useEffect, useState } from "react";
import { Loader2, Star, Target, X } from "lucide-react";

import { updateWishlistItem, type WishlistItemDetail } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Props = {
  item: WishlistItemDetail;
  onClose: () => void;
  onSaved: (updated: Partial<WishlistItemDetail>) => void;
};

/**
 * Modal for editing wishlist item meta — priority (1-5 star slider),
 * target price ceiling, free-form notes. Triggered by the ⚙ button on each
 * wishlist row.
 */
export function WishlistTargetModal({ item, onClose, onSaved }: Props) {
  const [priority, setPriority] = useState(item.priority);
  const [maxPriceStr, setMaxPriceStr] = useState(
    item.max_price_usd != null ? item.max_price_usd.toFixed(2) : "",
  );
  const [notes, setNotes] = useState(item.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Close on Escape key.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const market = item.market_price_usd;
  const targetNum = parseFloat(maxPriceStr);
  const targetValid = !maxPriceStr || (!Number.isNaN(targetNum) && targetNum >= 0);
  const wouldMeet =
    market != null && targetValid && targetNum > 0 && market <= targetNum;
  const discount =
    market != null && targetValid && targetNum > 0
      ? ((market - targetNum) / market) * 100
      : null;

  const onSave = async () => {
    if (!targetValid) {
      setErr("Target price must be a non-negative number");
      return;
    }
    setSaving(true);
    setErr(null);
    const payload = {
      priority,
      max_price_usd: maxPriceStr ? targetNum : null,
      notes: notes.trim() || null,
    };
    try {
      await updateWishlistItem(item.id, payload);
      onSaved({
        priority: payload.priority,
        max_price_usd: payload.max_price_usd,
        notes: payload.notes,
        target_met: !!(
          payload.max_price_usd != null &&
          market != null &&
          market <= payload.max_price_usd
        ),
      });
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
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
        className="w-full max-w-md rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/20 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-text-primary truncate">
              {item.card_name}
            </h2>
            <p className="text-xs text-text-tertiary font-mono mt-0.5 truncate">
              {item.set_name} · #{item.card_number ?? "—"}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-full text-text-tertiary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          {/* Priority */}
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
              Priority
            </label>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  onClick={() => setPriority(n)}
                  className="p-1 transition-transform hover:scale-110"
                  aria-label={`Set priority ${n}`}
                  title={`Priority ${n}`}
                >
                  <Star
                    className={cn(
                      "h-6 w-6 transition-colors",
                      n <= priority
                        ? "text-accent-yellow fill-accent-yellow"
                        : "text-text-tertiary",
                    )}
                  />
                </button>
              ))}
              <span className="ml-2 text-xs font-mono text-text-tertiary">
                {priority === 5
                  ? "must-have"
                  : priority >= 4
                    ? "want bad"
                    : priority === 3
                      ? "neutral"
                      : priority === 2
                        ? "casual"
                        : "low"}
              </span>
            </div>
          </div>

          {/* Target price */}
          <div>
            <label
              htmlFor="max-price"
              className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
            >
              Target price (USD)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary text-sm font-mono">
                $
              </span>
              <input
                id="max-price"
                type="number"
                step="0.01"
                min="0"
                value={maxPriceStr}
                onChange={(e) => setMaxPriceStr(e.target.value)}
                placeholder={market != null ? `e.g. ${(market * 0.85).toFixed(2)}` : "e.g. 50.00"}
                className="w-full rounded-full bg-bg border border-border pl-7 pr-3 py-2.5 text-sm font-mono focus:outline-none focus:border-rose-400/60 focus:ring-2 focus:ring-rose-400/15 transition-colors"
              />
            </div>
            <div className="mt-2 flex items-center gap-2 text-[11px] font-mono">
              {market != null && (
                <span className="text-text-tertiary">
                  Market: <span className="text-text-secondary">${market.toFixed(2)}</span>
                </span>
              )}
              {wouldMeet && (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-2 py-0.5 font-bold uppercase tracking-wider">
                  <Target className="h-2.5 w-2.5" /> Already at target
                </span>
              )}
              {!wouldMeet && discount != null && discount > 0 && (
                <span className="text-text-tertiary">
                  ↓ {discount.toFixed(1)}% from market
                </span>
              )}
            </div>
            <p className="mt-2 text-[11px] text-text-tertiary">
              Leave blank to track without a target. When price drops below your target,
              this card gets a Target met badge.
            </p>
          </div>

          {/* Notes */}
          <div>
            <label
              htmlFor="notes"
              className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
            >
              Notes <span className="lowercase opacity-70">(optional)</span>
            </label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="Saving for birthday · only NM · trade with Sam first"
              className="w-full rounded-2xl bg-bg border border-border px-3 py-2 text-sm focus:outline-none focus:border-rose-400/60 focus:ring-2 focus:ring-rose-400/15 transition-colors resize-none"
            />
            <p className="mt-1 text-[10px] text-text-tertiary text-right">
              {notes.length} / 500
            </p>
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
            onClick={onSave}
            disabled={saving || !targetValid}
            className="inline-flex items-center gap-2 rounded-full bg-rose-500 text-white font-bold px-5 py-2 text-sm hover:brightness-110 shadow-md shadow-rose-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
