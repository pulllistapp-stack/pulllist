"use client";

/**
 * /portfolio/slabs — user's graded cards rendered inside SlabFrame.
 *
 * Reuses listMyItems() and filters is_graded=true. The grade field is
 * stored as "PSA 10" / "BGS 9.5" etc. — same split logic as the edit
 * modal. Top-of-page toggle switches the frame PNG (BGS vs PSA); the
 * grader shown on each slab still reflects what the item actually is.
 */

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import {
  SERVICE_LOGO,
  SERVICE_LOGO_PILL_CLASS,
  SlabFrame,
} from "@/components/portfolio/SlabFrame";
import { CollectionItemDetail, listMyItems } from "@/lib/auth";

type FrameStyle = "bgs" | "psa" | "clean";
type GradeService = "PSA" | "BGS" | "CGC" | "TAG";

const SERVICE_SET = new Set<GradeService>(["PSA", "BGS", "CGC", "TAG"]);

const GRADE_SUFFIX: Record<string, string> = {
  "10": "Gem Mint",
  "9.5": "Mint+",
  "9": "Mint",
};

function splitGrade(grade: string | null): {
  service: GradeService;
  value: string;
  suffix?: string;
} {
  const fallback = { service: "PSA" as const, value: "10", suffix: GRADE_SUFFIX["10"] };
  if (!grade?.trim()) return fallback;
  // Match "PSA 10", "BGS 9.5 Gem Mint", "Ace 9", etc. The optional
  // trailing group captures a written-out suffix if one was stored.
  const m = grade.trim().match(/^(\S+)\s+(\S+)(?:\s+(.+))?$/);
  if (!m) return { service: "PSA", value: grade.trim() };
  const svcRaw = m[1].toUpperCase();
  const svc: GradeService = SERVICE_SET.has(svcRaw as GradeService)
    ? (svcRaw as GradeService)
    : "PSA";
  const value = m[2];
  const suffix = m[3]?.trim() || GRADE_SUFFIX[value];
  return { service: svc, value, suffix };
}

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export default function SlabsPortfolioPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<CollectionItemDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [frameStyle, setFrameStyle] = useState<FrameStyle>("psa");

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=/portfolio/slabs");
      return;
    }
    let cancelled = false;
    setLoading(true);
    listMyItems()
      .then((rows) => {
        if (!cancelled) setItems(rows.filter((r) => r.is_graded));
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, router]);

  const totalValue = useMemo(
    () => items.reduce((sum, it) => sum + (it.market_price_usd ?? 0) * it.qty, 0),
    [items],
  );

  if (authLoading || loading) {
    return (
      <main className="mx-auto max-w-[100rem] px-4 py-8">
        <PortfolioTabs active="slabs" />
        <div className="flex justify-center py-16">
          <MascotLoader />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <PortfolioTabs active="slabs" />

      <header className="mb-6 rounded-card border border-border bg-bg-surface/70 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-baseline gap-8">
            <div>
              <div className="text-3xl font-extrabold text-text-primary">
                {items.length}
              </div>
              <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                Graded cards
              </div>
            </div>
            <div>
              <div className="text-3xl font-extrabold text-accent-green">
                {fmtPrice(totalValue)}
              </div>
              <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                Est. value
              </div>
            </div>
          </div>

          {/* Frame style toggle */}
          <div
            role="tablist"
            aria-label="Frame style"
            className="flex items-center gap-1 p-1 rounded-full bg-bg border border-border"
          >
            {(["bgs", "psa", "clean"] as const).map((s) => (
              <button
                key={s}
                role="tab"
                aria-selected={frameStyle === s}
                onClick={() => setFrameStyle(s)}
                className={
                  "px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-full transition-colors " +
                  (frameStyle === s
                    ? "bg-accent-yellow text-gray-900 font-bold"
                    : "text-text-secondary hover:text-text-primary")
                }
              >
                {s === "bgs" ? "BGS frame" : s === "psa" ? "PSA frame" : "Clean frame"}
              </button>
            ))}
          </div>
        </div>
      </header>

      {items.length === 0 ? (
        <div className="rounded-card border border-dashed border-border/60 bg-bg-surface/40 p-8 text-center">
          <div className="text-sm font-semibold text-text-secondary">
            No graded cards yet
          </div>
          <div className="mt-1 text-xs text-text-tertiary">
            Mark any collection item as graded (with a PSA / BGS / CGC / TAG grade) and it shows up slabbed here.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {items.map((it) => {
            const { service, value, suffix } = splitGrade(it.grade);
            const setName = (it.set_name || it.set_id).toUpperCase();
            const yearSet = it.card_number
              ? `${setName} · #${it.card_number}`
              : setName;
            return (
              <Link
                key={it.id}
                href={`/cards/${it.card_id}`}
                className="group block"
              >
                <SlabFrame
                  style={frameStyle}
                  cardName={it.card_name}
                  cardImage={it.image_small ?? undefined}
                  yearSet={yearSet}
                  service={service}
                  grade={value}
                  suffix={suffix}
                />
                <div className="mt-3 flex items-center justify-between gap-2 px-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <div
                      className={
                        "relative h-6 w-14 shrink-0 flex items-center " +
                        SERVICE_LOGO_PILL_CLASS[service]
                      }
                    >
                      <Image
                        src={SERVICE_LOGO[service]}
                        alt={service}
                        fill
                        sizes="56px"
                        quality={100}
                        style={{ objectFit: "contain", objectPosition: "left center" }}
                      />
                    </div>
                    {suffix && (
                      <span className="text-[11px] font-mono uppercase tracking-[0.12em] text-text-tertiary truncate">
                        · {suffix}
                      </span>
                    )}
                    {it.qty > 1 && (
                      <span className="text-[11px] font-mono text-accent-yellow shrink-0">
                        ×{it.qty}
                      </span>
                    )}
                  </div>
                  <span className="text-[13px] font-mono font-bold text-accent-green tabular-nums shrink-0">
                    {fmtPrice(it.market_price_usd)}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </main>
  );
}
