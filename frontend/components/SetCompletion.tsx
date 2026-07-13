"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { useCollection } from "./CollectionProvider";
import { setCompletion, SetCompletion as SetCompletionData } from "@/lib/auth";

type Props = {
  setId: string;
  masterTotal: number;
  fullSetTotal: number;
};

/**
 * Header progress widget on /sets/[id]. Two collection frames side by
 * side — Full Set (base numbered run, from Set.printed_total) and
 * Master (every card including secrets / hyper rares).
 *
 * Logged-out users see set metrics + a soft "Log in" nudge; totals
 * teach the reader what's in the set before any auth wall. Logged-in
 * users see live owned counts with a Master completion ring on the
 * left and Full Set / Master progress bars below.
 */
export function SetCompletion({ setId, masterTotal, fullSetTotal }: Props) {
  const { user } = useAuth();
  const { ownedSet } = useCollection();
  const [data, setData] = useState<SetCompletionData | null>(null);

  useEffect(() => {
    if (!user) {
      setData(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const d = await setCompletion(setId);
        if (!cancelled) setData(d);
      } catch {
        if (!cancelled) setData(null);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Re-fetch when the user toggles cards in this set.
    // We watch ownedSet membership for this set rather than the whole
    // Set object (which changes on every toggle) to avoid unnecessary
    // network calls.
  }, [setId, user, ownedSet]);

  const masterOwned = data?.master_owned ?? 0;
  const masterActualTotal = data?.master_total ?? masterTotal;
  const fullSetOwned = data?.full_set_owned ?? 0;
  const fullSetActualTotal = data?.full_set_total ?? fullSetTotal;
  const value = data?.estimated_value_usd ?? 0;

  const masterPct =
    masterActualTotal > 0
      ? Math.round((masterOwned / masterActualTotal) * 1000) / 10
      : 0;
  const fullSetPct =
    fullSetActualTotal > 0
      ? Math.round((fullSetOwned / fullSetActualTotal) * 1000) / 10
      : 0;

  return (
    <section className="rounded-card border border-border bg-bg-surface/70 p-5">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:gap-8">
        <ProgressRing pct={masterPct} disabled={!user} />

        <div className="flex flex-1 flex-wrap items-center gap-6 md:gap-10">
          <Stat
            label="Master Owned"
            value={user ? masterOwned : "—"}
            subtle={!user}
          />
          <Stat
            label="Master Total"
            value={masterActualTotal}
            accent
          />
          <Stat
            label="Full Set Owned"
            value={user ? fullSetOwned : "—"}
            subtle={!user}
          />
          <Stat
            label="Full Set Total"
            value={fullSetActualTotal}
            accent
          />
          {user && value > 0 && (
            <Stat
              label="Est. Value"
              value={`$${value.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}`}
              accent
            />
          )}
        </div>

        {!user && (
          <div className="flex-shrink-0">
            <Link
              href="/login"
              className="inline-flex items-center gap-1.5 rounded-btn bg-accent-yellow px-4 py-2 text-sm font-semibold text-gray-900 hover:brightness-110"
            >
              Sign in
            </Link>
          </div>
        )}
      </div>

      <div className="mt-6 space-y-3">
        <ProgressBar
          label="Full Set"
          owned={user ? fullSetOwned : 0}
          total={fullSetActualTotal}
          pct={user ? fullSetPct : 0}
          colorClass="from-accent-red/70 to-accent-red"
        />
        <ProgressBar
          label="Master"
          owned={user ? masterOwned : 0}
          total={masterActualTotal}
          pct={user ? masterPct : 0}
          colorClass="from-teal-400/70 to-teal-400"
        />
      </div>

      {fullSetActualTotal < masterActualTotal && (
        <div className="mt-4 text-[11px] leading-relaxed text-text-tertiary">
          Full Set counts the {fullSetActualTotal} base numbered cards.
          Master adds{" "}
          <span className="font-mono text-text-secondary">
            {masterActualTotal - fullSetActualTotal}
          </span>{" "}
          secret / SIR / hyper-rare card
          {masterActualTotal - fullSetActualTotal === 1 ? "" : "s"} on top.
        </div>
      )}
    </section>
  );
}

function ProgressRing({
  pct,
  disabled = false,
}: {
  pct: number;
  disabled?: boolean;
}) {
  const size = 88;
  const stroke = 8;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, pct));
  const offset = circumference * (1 - clamped / 100);
  return (
    <div
      className="relative flex-shrink-0"
      style={{ width: size, height: size }}
      aria-label={`Master completion ${clamped}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          className="text-border/60"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={
            disabled
              ? "text-text-tertiary/40 transition-all duration-500"
              : "text-accent-yellow transition-all duration-500"
          }
        />
      </svg>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <div
          className={
            "text-lg font-extrabold leading-none " +
            (disabled ? "text-text-tertiary" : "text-text-primary")
          }
        >
          {clamped.toFixed(0)}%
        </div>
        <div className="mt-1 text-[9px] font-mono uppercase tracking-wider text-text-tertiary">
          Master
        </div>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  accent = false,
  subtle = false,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
  subtle?: boolean;
}) {
  return (
    <div className="flex flex-col items-start">
      <div
        className={
          "text-2xl font-extrabold leading-none " +
          (subtle
            ? "text-text-tertiary"
            : accent
              ? "text-text-primary"
              : "text-accent-green")
        }
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
        {label}
      </div>
    </div>
  );
}

function ProgressBar({
  label,
  owned,
  total,
  pct,
  colorClass,
}: {
  label: string;
  owned: number;
  total: number;
  pct: number;
  colorClass: string;
}) {
  const filled = Math.max(0, Math.min(100, pct));
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-xs">
        <span className="font-semibold uppercase tracking-wider">
          <span
            className={
              label === "Full Set" ? "text-accent-red" : "text-teal-400"
            }
          >
            {label}
          </span>
        </span>
        <span className="font-mono text-text-secondary">
          {owned.toLocaleString()}
          <span className="text-text-tertiary">/{total.toLocaleString()}</span>
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-bg">
        <div
          className={
            "h-full rounded-full bg-gradient-to-r transition-all duration-500 " +
            colorClass
          }
          style={{ width: `${filled}%` }}
        />
      </div>
    </div>
  );
}
