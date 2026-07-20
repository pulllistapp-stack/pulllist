/**
 * Frontend mirror of backend `app.services.graded_pricing.user_grade_to_key`.
 * Maps a (service, value) selection from the Add/Edit collection modals to
 * the canonical tier key used by /cards/{id}/graded-prices so the modal
 * can show the correct live market for the slab the user is describing.
 *
 * Keep in lockstep with the backend classifier — a mismatch here means
 * the modal shows one price while the vault row values it at a different
 * tier.
 */

export type GradedTierPayload = {
  latest_price_usd: number | null;
  variant?: string | null;
  source: string | null;
  updated_at: string | null;
  sales_count?: number | null;
};

export type GradedPricesResponse = Partial<
  Record<string, GradedTierPayload | null>
> & {
  _meta?: { last_scraped_at: string | null; days_window: number };
};

export const GRADE_SERVICES = ["PSA", "BGS", "CGC", "TAG", "SGC", "Ace"];

export function serviceGradeToKey(
  service: string,
  value: string,
): string | null {
  const s = (service || "").trim().toUpperCase();
  const v = (value || "").trim();
  if (s === "PSA") {
    if (v === "10") return "psa10";
    if (v === "9") return "psa9";
    return null;
  }
  if (s === "CGC") {
    if (v === "10" || /pristine/i.test(v)) return "cgc10";
    if (v === "9") return "cgc9";
    return null;
  }
  if (s === "BGS") {
    if (/black\s*label/i.test(v)) return "bgs10bl";
    if (v === "10") return "bgs10";
    if (v === "9.5") return "bgs9.5";
    if (v === "9") return "bgs9";
    return null;
  }
  if (s === "TAG") {
    if (v === "10") return "tag10";
    if (v === "9.5") return "tag9.5";
    if (v === "9") return "tag9";
    return null;
  }
  return null;
}

export function fmtGradedMoney(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 1000)
    return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}
