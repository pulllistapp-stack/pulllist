"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { useCollection } from "./CollectionProvider";
import { setCompletion, SetCompletion as SetCompletionData } from "@/lib/auth";

type Props = {
  setId: string;
  totalCards: number;
};

export function SetCompletion({ setId, totalCards }: Props) {
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
    // We watch ownedSet membership for this set rather than the whole Set object
    // (which changes on every toggle) to avoid unnecessary network calls.
  }, [setId, user, ownedSet]);

  if (!user) {
    return (
      <div className="rounded-card border border-border bg-bg-surface p-4 max-w-md">
        <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary mb-1">
          Your collection
        </div>
        <div className="text-sm text-text-secondary">
          <Link href="/login" className="text-accent-yellow hover:underline">
            Log in
          </Link>{" "}
          to track your progress on this set.
        </div>
      </div>
    );
  }

  const owned = data?.owned_unique ?? 0;
  const pct = data?.completion_pct ?? 0;
  const value = data?.estimated_value_usd ?? 0;

  return (
    <div className="rounded-card border border-border bg-bg-surface p-4 max-w-md">
      <div className="flex items-baseline justify-between mb-3">
        <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
          Your collection
        </div>
        <div className="text-xs font-mono text-text-tertiary">
          ${value.toFixed(2)} est.
        </div>
      </div>

      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-bold font-mono text-accent-green">
          {pct.toFixed(1)}%
        </span>
        <span className="text-sm text-text-secondary font-mono">
          {owned} / {totalCards}
        </span>
      </div>

      <div className="h-2 rounded-full bg-bg overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-accent-green/80 to-accent-green transition-all duration-500"
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
    </div>
  );
}
