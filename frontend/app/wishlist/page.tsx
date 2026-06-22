"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  Bell,
  Heart,
  Settings2,
  Sparkles,
  Target,
  Trash2,
  TrendingDown,
} from "lucide-react";

import { MascotLoader } from "@/components/MascotLoader";
import { RarityChip } from "@/components/RarityChip";
import { useAuth } from "@/components/AuthProvider";
import { useWishlist } from "@/components/WishlistProvider";
import { WishlistTargetModal } from "@/components/WishlistTargetModal";
import {
  deleteWishlistItem,
  listMyWishlist,
  wishlistSummary,
  type WishlistItemDetail,
  type WishlistSummary,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

type FilterMode = "all" | "at_target";

export default function WishlistPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { refresh: refreshWishlist } = useWishlist();
  const [items, setItems] = useState<WishlistItemDetail[] | null>(null);
  const [summary, setSummary] = useState<WishlistSummary | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<WishlistItemDetail | null>(null);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login?redirect=/wishlist");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([listMyWishlist(), wishlistSummary()])
      .then(([its, sum]) => {
        if (cancelled) return;
        setItems(its);
        setSummary(sum);
      })
      .catch((e) => {
        if (!cancelled) setErr(String(e?.message ?? e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const filtered = useMemo(() => {
    if (!items) return [];
    if (filter === "at_target") return items.filter((i) => i.target_met);
    return items;
  }, [items, filter]);

  const onRemove = async (itemId: number) => {
    setItems((prev) => (prev ? prev.filter((i) => i.id !== itemId) : prev));
    try {
      await deleteWishlistItem(itemId);
      await refreshWishlist();
      const sum = await wishlistSummary().catch(() => null);
      if (sum) setSummary(sum);
    } catch {
      // revert by refetching on failure
      const its = await listMyWishlist().catch(() => null);
      if (its) setItems(its);
    }
  };

  if (authLoading || !user) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-16">
        <MascotLoader size="lg" />
      </main>
    );
  }

  return (
    <main className="relative mx-auto max-w-6xl px-4 py-10 sm:py-14">
      {/* Atmospheric glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/3 h-80 w-80 rounded-full bg-rose-400/10 blur-3xl"
      />

      {/* Hero */}
      <div className="relative mb-8 flex items-center gap-3">
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/15 text-rose-500">
          <Heart className="h-6 w-6 fill-current" />
        </span>
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
            Wishlist
          </h1>
          <p className="text-sm text-text-secondary">
            Cards you&apos;re chasing — set a target price and we&apos;ll flag when
            the market moves.
          </p>
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="mb-8 grid grid-cols-2 sm:grid-cols-3 gap-3">
          <StatTile
            icon={<Heart className="h-4 w-4 text-rose-500" />}
            label="On wishlist"
            value={summary.total.toString()}
            sub="cards"
          />
          <StatTile
            icon={<Sparkles className="h-4 w-4 text-amber-500" />}
            label="Est. total"
            value={`$${summary.estimated_value_usd.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}`}
            sub="at current market"
          />
          <StatTile
            icon={<Target className="h-4 w-4 text-accent-green" />}
            label="At target"
            value={summary.at_target_count.toString()}
            sub="ready to buy"
            highlight={summary.at_target_count > 0}
          />
        </div>
      )}

      {/* Filter row */}
      {items && items.length > 0 && (
        <div className="mb-5 inline-flex rounded-full border border-border bg-bg-surface p-1">
          <FilterPill
            active={filter === "all"}
            onClick={() => setFilter("all")}
          >
            All {items.length}
          </FilterPill>
          <FilterPill
            active={filter === "at_target"}
            onClick={() => setFilter("at_target")}
            accent="green"
          >
            <Target className="h-3.5 w-3.5" /> At target{" "}
            {items.filter((i) => i.target_met).length}
          </FilterPill>
        </div>
      )}

      {err && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-4">
          {err}
        </div>
      )}

      {loading && <MascotLoader size="lg" className="py-8" />}

      {!loading && items && items.length === 0 && <EmptyState />}

      {!loading && items && items.length > 0 && filtered.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border bg-bg-surface/50 p-8 text-center">
          <p className="text-sm text-text-secondary">
            None of your wishlisted cards are at target yet. Watch this space —
            the daily cron updates prices every morning.
          </p>
        </div>
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map((item) => (
            <WishlistRow
              key={item.id}
              item={item}
              onRemove={onRemove}
              onEdit={() => setEditing(item)}
            />
          ))}
        </div>
      )}

      {editing && (
        <WishlistTargetModal
          item={editing}
          onClose={() => setEditing(null)}
          onSaved={(updated) => {
            setItems((prev) =>
              prev
                ? prev.map((i) =>
                    i.id === editing.id ? { ...i, ...updated } : i,
                  )
                : prev,
            );
            // Summary may shift (at_target count) — refetch in background.
            void wishlistSummary().then(setSummary).catch(() => {});
          }}
        />
      )}
    </main>
  );
}

// ────────── components ──────────

function StatTile({
  icon,
  label,
  value,
  sub,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-bg-surface p-4",
        highlight
          ? "border-accent-green/40 shadow-sm shadow-accent-green/10"
          : "border-border",
      )}
    >
      <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
        {icon}
        {label}
      </div>
      <p className="mt-2 text-2xl font-extrabold text-text-primary">{value}</p>
      {sub && <p className="text-[11px] font-mono text-text-tertiary">{sub}</p>}
    </div>
  );
}

function FilterPill({
  active,
  accent,
  onClick,
  children,
}: {
  active: boolean;
  accent?: "green";
  onClick: () => void;
  children: React.ReactNode;
}) {
  const activeCls =
    accent === "green"
      ? "bg-accent-green/15 text-accent-green shadow-sm shadow-accent-green/20"
      : "bg-bg-elevated text-text-primary shadow-sm";
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
        active ? activeCls : "text-text-secondary hover:text-text-primary",
      )}
    >
      {children}
    </button>
  );
}

function WishlistRow({
  item,
  onRemove,
  onEdit,
}: {
  item: WishlistItemDetail;
  onRemove: (id: number) => void;
  onEdit: () => void;
}) {
  const market = item.market_price_usd;
  const target = item.max_price_usd;
  const targetMet = item.target_met;

  return (
    <div
      className={cn(
        "group relative flex gap-3 rounded-2xl border bg-bg-surface p-3 transition-all duration-200",
        targetMet
          ? "border-accent-green/40 shadow-sm shadow-accent-green/10 hover:shadow-md hover:shadow-accent-green/20"
          : "border-border hover:border-rose-400/40",
      )}
    >
      <Link
        href={`/cards/${item.card_id}`}
        className="relative h-28 w-20 shrink-0 overflow-hidden rounded-md bg-bg"
      >
        {item.image_small ? (
          <Image
            src={item.image_small}
            alt={item.card_name}
            fill
            className="object-contain"
            sizes="80px"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-text-tertiary">
            no image
          </div>
        )}
      </Link>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <Link
              href={`/cards/${item.card_id}`}
              className="truncate text-sm font-bold text-text-primary hover:text-rose-500 transition-colors block"
            >
              {item.card_name}
            </Link>
            <p className="text-xs text-text-tertiary font-mono truncate mt-0.5">
              {item.set_name} · #{item.card_number ?? "—"}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={onEdit}
              className="text-text-tertiary hover:text-rose-500 transition-colors p-1"
              title="Edit target & priority"
              aria-label="Edit wishlist item"
            >
              <Settings2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => onRemove(item.id)}
              className="text-text-tertiary hover:text-accent-red transition-colors p-1"
              title="Remove from wishlist"
              aria-label="Remove from wishlist"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {item.rarity && (
          <div className="mt-1.5">
            <RarityChip rarity={item.rarity} />
          </div>
        )}

        <div className="mt-2.5 grid grid-cols-2 gap-2 text-xs">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Market
            </p>
            <p className="font-mono font-bold text-text-primary">
              {market != null ? `$${market.toFixed(2)}` : "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              Target
            </p>
            <p
              className={cn(
                "font-mono font-bold",
                target != null
                  ? targetMet
                    ? "text-accent-green"
                    : "text-text-primary"
                  : "text-text-tertiary",
              )}
            >
              {target != null ? `$${target.toFixed(2)}` : "no target"}
            </p>
          </div>
        </div>

        {targetMet && (
          <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-accent-green/15 text-accent-green border border-accent-green/30 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider">
            <Bell className="h-2.5 w-2.5" /> Target met
          </div>
        )}

        {market != null &&
          target != null &&
          !targetMet &&
          market > target && (
            <div className="mt-2 inline-flex items-center gap-1 text-[11px] font-mono text-text-tertiary">
              <TrendingDown className="h-3 w-3" />
              {`$${(market - target).toFixed(2)} above target`}
            </div>
          )}
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex gap-3 rounded-2xl border border-border bg-bg-surface p-3 animate-pulse"
        >
          <div className="h-28 w-20 shrink-0 rounded-md bg-bg" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-3/4 rounded bg-bg" />
            <div className="h-2 w-1/2 rounded bg-bg" />
            <div className="h-2 w-1/3 rounded bg-bg" />
            <div className="h-5 w-2/3 rounded bg-bg mt-3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-3xl border-2 border-dashed border-border bg-bg-surface/50 p-16 text-center">
      <div className="mx-auto mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full bg-rose-500/10 text-rose-500">
        <Heart className="h-8 w-8" />
      </div>
      <h2 className="text-xl font-bold text-text-primary">Your wishlist is empty</h2>
      <p className="mt-2 text-sm text-text-secondary max-w-md mx-auto">
        Tap the heart on any card to save it here. Set a target price and we&apos;ll
        track when it drops.
      </p>
      <Link
        href="/cards"
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-rose-500 text-white font-bold px-5 py-2.5 text-sm hover:brightness-110 shadow-md shadow-rose-500/30 transition-all"
      >
        Browse cards
        <ArrowRight className="h-4 w-4" aria-hidden />
      </Link>
    </div>
  );
}
