"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import {
  BinderSize,
  BinderView,
  MasterSetDisplayMode,
  MasterSetSortMode,
  getBinderView,
  updateMasterSet,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

const BINDER_COLS: Record<BinderSize, number> = {
  "3x3": 3,
  "4x3": 4,
  "4x4": 4,
};

export default function BinderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const masterSetId = Number(params?.id);

  const [view, setView] = useState<BinderView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<MasterSetDisplayMode | null>(null);
  const [sort, setSort] = useState<MasterSetSortMode | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(
    async (m: MasterSetDisplayMode | null, s: MasterSetSortMode | null) => {
      const token = getToken();
      if (!token || !Number.isFinite(masterSetId)) return;
      try {
        const next = await getBinderView(
          masterSetId,
          { mode: m ?? undefined, sort: s ?? undefined },
          token,
        );
        setView(next);
        if (m === null) setMode(next.master_set.display_mode);
        if (s === null) setSort(next.master_set.sort_mode);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    },
    [masterSetId],
  );

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace(`/login?next=/portfolio/masters/${masterSetId}`);
      return;
    }
    reload(null, null);
  }, [authLoading, user, router, reload, masterSetId]);

  const flipMode = async (next: MasterSetDisplayMode) => {
    setMode(next);
    setBusy(true);
    try {
      await reload(next, sort);
      const token = getToken();
      if (token) await updateMasterSet(masterSetId, { display_mode: next }, token);
    } finally {
      setBusy(false);
    }
  };

  const flipSort = async (next: MasterSetSortMode) => {
    setSort(next);
    setBusy(true);
    try {
      await reload(mode, next);
      const token = getToken();
      if (token) await updateMasterSet(masterSetId, { sort_mode: next }, token);
    } finally {
      setBusy(false);
    }
  };

  const flipBinderSize = async (next: BinderSize) => {
    const token = getToken();
    if (!token || !view) return;
    setBusy(true);
    try {
      const updated = await updateMasterSet(
        masterSetId,
        { binder_size: next },
        token,
      );
      setView({ ...view, master_set: updated });
    } finally {
      setBusy(false);
    }
  };

  const pct = useMemo(() => {
    if (!view || !mode) return 0;
    const owned =
      mode === "master" ? view.master_set.owned_master : view.master_set.owned_base;
    const total =
      mode === "master" ? view.master_set.total_master : view.master_set.total_base;
    return total ? Math.round((owned / total) * 100) : 0;
  }, [view, mode]);

  const complete = pct === 100 && view !== null && view.slots.length > 0;

  if (authLoading || !user || !view) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-10">
        <MascotLoader size="lg" className="py-12" />
        {error && (
          <div className="mt-4 rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm">
            <div className="font-semibold mb-1">Failed to load</div>
            <div className="text-text-secondary font-mono">{error}</div>
          </div>
        )}
      </main>
    );
  }

  const cols = BINDER_COLS[view.master_set.binder_size];

  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/portfolio" className="hover:text-text-primary">
          Portfolio
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/portfolio/masters" className="hover:text-text-primary">
          Master Sets
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">{view.master_set.set_name}</span>
      </nav>

      <PortfolioTabs active="masters" />

      <header className="mb-6 flex items-start gap-4 flex-wrap">
        {view.master_set.set_logo_url ? (
          <div className="relative h-16 w-24 shrink-0 flex items-center justify-center">
            <Image
              src={view.master_set.set_logo_url}
              alt=""
              width={96}
              height={64}
              className="max-h-16 w-auto object-contain"
              unoptimized
            />
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {view.master_set.set_name}
          </h1>
          <p className="text-sm text-text-secondary">
            {view.master_set.set_release_date ?? "Release TBD"} · Base{" "}
            {view.master_set.owned_base}/{view.master_set.total_base} · Master{" "}
            {view.master_set.owned_master}/{view.master_set.total_master}
          </p>
        </div>
        <Link
          href={`/sets/${view.master_set.set_id}`}
          className="text-xs text-text-secondary hover:text-text-primary underline decoration-dotted"
        >
          Browse full set →
        </Link>
      </header>

      <section
        className={
          "mb-6 rounded-card border p-4 " +
          (complete
            ? "border-accent-green/60 bg-accent-green/10"
            : "border-border bg-bg-surface")
        }
      >
        <div className="flex items-baseline justify-between mb-2">
          <div className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            {mode === "master" ? "Master completion" : "Base completion"}
          </div>
          <div className="font-mono tabular-nums text-lg">
            {pct}%
          </div>
        </div>
        <div className="h-3 w-full rounded-full bg-bg overflow-hidden">
          <div
            className={
              "h-full transition-[width] duration-700 " +
              (complete ? "bg-accent-green" : "bg-accent-yellow")
            }
            style={{ width: `${pct}%` }}
          />
        </div>
        {complete && (
          <div className="mt-3 text-sm font-semibold text-accent-green flex items-center gap-2">
            <span aria-hidden>✨</span>
            Completed — every slot filled!
          </div>
        )}
      </section>

      <section className="mb-4 flex flex-wrap items-center gap-2">
        <ToggleGroup
          label="View"
          value={mode ?? "base"}
          options={[
            { value: "base", label: "Base" },
            { value: "master", label: "Master" },
          ]}
          onChange={(v) => flipMode(v as MasterSetDisplayMode)}
          disabled={busy}
        />
        <ToggleGroup
          label="Sort"
          value={sort ?? "number"}
          options={[
            { value: "number", label: "Number" },
            { value: "rarity", label: "Rarity" },
          ]}
          onChange={(v) => flipSort(v as MasterSetSortMode)}
          disabled={busy}
        />
        <ToggleGroup
          label="Binder"
          value={view.master_set.binder_size}
          options={[
            { value: "3x3", label: "3×3" },
            { value: "4x3", label: "4×3" },
            { value: "4x4", label: "4×4" },
          ]}
          onChange={(v) => flipBinderSize(v as BinderSize)}
          disabled={busy}
        />
      </section>

      <section
        className="grid gap-2"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {view.slots.map((slot, idx) => (
          <BinderSlotCell key={`${slot.card_id}-${slot.variant}-${idx}`} slot={slot} />
        ))}
      </section>

      {view.slots.length === 0 && (
        <div className="rounded-card border border-dashed border-border bg-bg-surface p-8 text-center text-sm text-text-secondary">
          This set has no cards catalogued yet.
        </div>
      )}
    </main>
  );
}

function ToggleGroup({
  label,
  value,
  options,
  onChange,
  disabled,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className="text-xs uppercase tracking-wider text-text-tertiary">
        {label}
      </span>
      <div
        role="tablist"
        aria-label={label}
        className="inline-flex rounded-btn border border-border bg-bg-surface overflow-hidden"
      >
        {options.map((o) => {
          const active = o.value === value;
          return (
            <button
              key={o.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(o.value)}
              disabled={disabled}
              className={
                "px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 " +
                (active
                  ? "bg-accent-yellow text-bg"
                  : "text-text-secondary hover:text-text-primary")
              }
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function BinderSlotCell({
  slot,
}: {
  slot: BinderView["slots"][number];
}) {
  const label =
    slot.variant === "base"
      ? null
      : slot.variant === "reverseHolofoil"
        ? "Reverse"
        : slot.variant === "holofoil"
          ? "Holo"
          : slot.variant === "1stEdition"
            ? "1st Ed"
            : slot.variant === "1stEditionHolofoil"
              ? "1st Ed Holo"
              : slot.variant === "unlimitedHolofoil"
                ? "Unl. Holo"
                : slot.variant === "unlimited"
                  ? "Unlimited"
                  : slot.variant;
  return (
    <Link
      href={`/cards/${slot.card_id}`}
      title={`${slot.name}${label ? ` · ${label}` : ""}${slot.owned ? " · owned" : ""}`}
      className={
        "relative block aspect-[3/4] rounded-btn border overflow-hidden bg-bg-surface transition-transform hover:scale-[1.02] " +
        (slot.owned
          ? "border-accent-green/40"
          : "border-border")
      }
    >
      {slot.image_small ? (
        <Image
          src={slot.image_small}
          alt={slot.name}
          fill
          sizes="(max-width: 640px) 33vw, 20vw"
          className={"object-cover " + (slot.owned ? "" : "grayscale opacity-40")}
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center p-1 text-center">
          <div className="text-[10px] font-mono text-text-tertiary leading-tight">
            {slot.number ?? "—"}
            <br />
            {slot.name.slice(0, 18)}
          </div>
        </div>
      )}
      {slot.number && (
        <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[10px] font-mono text-white">
          {slot.number}
        </span>
      )}
      {label && (
        <span className="absolute right-1 top-1 rounded bg-accent-yellow/90 px-1 py-0.5 text-[9px] font-semibold uppercase text-bg tracking-wider">
          {label}
        </span>
      )}
      {slot.owned && (
        <span
          className="absolute bottom-1 right-1 flex h-5 w-5 items-center justify-center rounded-full bg-accent-green text-bg text-xs"
          aria-label="Owned"
        >
          ✓
        </span>
      )}
    </Link>
  );
}
