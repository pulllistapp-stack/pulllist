"use client";

import { useEffect, useState } from "react";
import { Check, Image as ImageIcon, Loader2, Tag, Type, X } from "lucide-react";

import {
  submitCardReport,
  type CardReportCategory,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

type Props = {
  cardId: string;
  cardName: string;
  cardNumber?: string | null;
  setName?: string | null;
  onClose: () => void;
};

const CATEGORIES: {
  value: CardReportCategory;
  label: string;
  hint: string;
  icon: typeof Tag;
}[] = [
  {
    value: "wrong_price",
    label: "Wrong price",
    hint: "Market price seems off or matches wrong listings",
    icon: Tag,
  },
  {
    value: "wrong_image",
    label: "Wrong image",
    hint: "Card art doesn't match what's printed",
    icon: ImageIcon,
  },
  {
    value: "wrong_name",
    label: "Wrong name",
    hint: "Card name or translation is incorrect",
    icon: Type,
  },
  {
    value: "other",
    label: "Other",
    hint: "Anything else — please describe below",
    icon: Tag,
  },
];

/** "Report an issue" modal on the card detail page. 4 categories +
 *  free-text comment. Comment required when category is 'other'.
 *  Anonymous submissions are allowed; the backend attributes to the
 *  signed-in user when a token is present. */
export function CardReportModal({
  cardId,
  cardName,
  cardNumber,
  setName,
  onClose,
}: Props) {
  const [category, setCategory] = useState<CardReportCategory | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const otherSelected = category === "other";
  const trimmedComment = comment.trim();
  const canSubmit =
    !!category && (!otherSelected || trimmedComment.length > 0);

  const onSubmit = async () => {
    if (!category || submitting) return;
    setSubmitting(true);
    setErr(null);
    try {
      await submitCardReport(cardId, {
        category,
        comment: trimmedComment || null,
      });
      setSubmitted(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Submit failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="card-report-title"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/30 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border">
          <div className="min-w-0">
            <p className="text-[10px] font-mono uppercase tracking-wider text-accent-red">
              Report an issue
            </p>
            <h2
              id="card-report-title"
              className="mt-0.5 text-lg font-bold text-text-primary truncate"
            >
              {cardName}
            </h2>
            {(setName || cardNumber) && (
              <p className="text-xs text-text-tertiary font-mono mt-0.5 truncate">
                {setName ?? ""}
                {setName && cardNumber ? " · " : ""}
                {cardNumber ? `#${cardNumber}` : ""}
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

        {/* Body — submitted state OR form */}
        {submitted ? (
          <div className="p-8 text-center">
            <div className="mx-auto h-14 w-14 rounded-full bg-accent-green/15 ring-4 ring-accent-green/20 flex items-center justify-center mb-4">
              <Check className="h-7 w-7 text-accent-green" />
            </div>
            <h3 className="text-base font-bold text-text-primary">
              Thanks for the report!
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              We&apos;ll review it and fix what&apos;s broken.
            </p>
            <button
              onClick={onClose}
              className="mt-5 rounded-full bg-accent-yellow text-gray-900 font-bold px-6 py-2 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2">
                  What&apos;s wrong?
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {CATEGORIES.map((c) => {
                    const active = category === c.value;
                    const Icon = c.icon;
                    return (
                      <button
                        key={c.value}
                        type="button"
                        onClick={() => setCategory(c.value)}
                        title={c.hint}
                        className={cn(
                          "flex items-center gap-2 rounded-card border px-3 py-2.5 text-left transition-colors",
                          active
                            ? "bg-accent-red/10 border-accent-red/60 text-accent-red"
                            : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-red/40",
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <span className="text-sm font-semibold">{c.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label
                  htmlFor="report-comment"
                  className="block text-xs font-mono uppercase tracking-wider text-text-tertiary mb-2"
                >
                  Details{" "}
                  {otherSelected ? (
                    <span className="text-accent-red lowercase">(required)</span>
                  ) : (
                    <span className="lowercase opacity-70">(optional)</span>
                  )}
                </label>
                <textarea
                  id="report-comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={3}
                  maxLength={1000}
                  placeholder={
                    otherSelected
                      ? "Describe the issue..."
                      : "Any extra context that would help us fix it"
                  }
                  className="w-full rounded-2xl bg-bg border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-red/60 focus:ring-2 focus:ring-accent-red/15 transition-colors resize-none"
                />
                <p className="mt-1 text-[10px] text-text-tertiary text-right">
                  {comment.length} / 1000
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
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="rounded-full border border-border px-4 py-2 text-sm font-semibold text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onSubmit}
                disabled={!canSubmit || submitting}
                className="inline-flex items-center gap-2 rounded-full bg-accent-red text-white font-bold px-5 py-2 text-sm hover:brightness-110 shadow-md shadow-accent-red/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
                Submit report
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
