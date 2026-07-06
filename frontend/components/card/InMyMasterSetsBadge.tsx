"use client";

import Image from "next/image";
import Link from "next/link";
import { BookMarked, ChevronRight, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { listMasterSetsForCard, type MasterSet } from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Renders on the card detail page. Fetches the caller's master sets
 * that contain this card (0 or 1 today — master sets are unique per
 * user+set). If one exists, links to the binder with a progress
 * summary; if not, offers a shortcut to create one for this card's set.
 *
 * Client-side so it can pull the JWT and avoid dragging auth state
 * into the server-rendered card page.
 */
export function InMyMasterSetsBadge({
  cardId,
  setId,
  setName,
}: {
  cardId: string;
  setId: string;
  setName: string | null;
}) {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<MasterSet[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !user) return;
    const token = getToken();
    if (!token) return;
    (async () => {
      try {
        setRows(await listMasterSetsForCard(cardId, token));
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed");
      }
    })();
  }, [authLoading, user, cardId]);

  if (!user || err) return null;
  if (rows === null) {
    return (
      <div className="rounded-card border border-border bg-bg-surface p-3 flex items-center gap-2 text-xs text-text-tertiary">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Checking your master sets…
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <Link
        href="/portfolio/masters"
        className="group flex items-center justify-between rounded-card border border-dashed border-border bg-bg-surface px-4 py-3 hover:border-accent-yellow/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-bg text-text-tertiary group-hover:text-accent-yellow transition-colors">
            <BookMarked className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-text-primary">
              Track {setName ?? "this set"} in a Master Set
            </div>
            <div className="text-xs text-text-tertiary">
              Watch every card in the set fill up like a binder page
            </div>
          </div>
        </div>
        <ChevronRight className="h-4 w-4 text-text-tertiary group-hover:text-accent-yellow transition-colors shrink-0" />
      </Link>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((m) => {
        const pct = m.total_base
          ? Math.round((m.owned_base / m.total_base) * 100)
          : 0;
        return (
          <Link
            key={m.id}
            href={`/portfolio/masters/${m.id}`}
            className="group flex items-center gap-3 rounded-card border border-border bg-bg-surface px-4 py-3 hover:border-accent-yellow/50 transition-colors"
          >
            {m.set_logo_url ? (
              <div className="relative h-9 w-14 shrink-0 flex items-center justify-center">
                <Image
                  src={m.set_logo_url}
                  alt=""
                  width={56}
                  height={36}
                  className="max-h-9 w-auto object-contain"
                  unoptimized
                />
              </div>
            ) : (
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-bg text-accent-yellow">
                <BookMarked className="h-4 w-4" />
              </div>
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs text-text-tertiary uppercase tracking-wider font-semibold">
                In your master set
              </div>
              <div className="text-sm font-semibold text-text-primary truncate">
                {m.set_name}
              </div>
              <div className="mt-1 flex items-center gap-2">
                <div className="h-1.5 flex-1 rounded-full bg-bg overflow-hidden">
                  <div
                    className={
                      "h-full transition-[width] duration-500 " +
                      (pct === 100 ? "bg-accent-green" : "bg-accent-yellow")
                    }
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="font-mono tabular-nums text-[11px] text-text-secondary shrink-0">
                  {m.owned_base}/{m.total_base} · {pct}%
                </div>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 text-text-tertiary group-hover:text-accent-yellow transition-colors shrink-0" />
          </Link>
        );
      })}
    </div>
  );
}
