"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { BinderSpread } from "@/components/portfolio/BinderSpread";
import { CompletionCelebration } from "@/components/portfolio/CompletionCelebration";
import { MasterSetShareModal } from "@/components/portfolio/MasterSetShareModal";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import {
  BinderSize,
  BinderView,
  MasterSetDisplayMode,
  MasterSetSortMode,
  clearMasterSetCover,
  getBinderView,
  setMasterSetCover,
  updateMasterSet,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { fileToResizedDataUrl } from "@/lib/image-resize";

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
  const [coverBusy, setCoverBusy] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [celebrating, setCelebrating] = useState(false);

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
        // Backend flags just_completed=true on the response that FIRST
        // stamps completed_at. Fire the celebration one-shot then let
        // it timeout naturally.
        if (next.master_set.just_completed) setCelebrating(true);
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

  const handleUploadCover = useCallback(
    async (file: File) => {
      const token = getToken();
      if (!token || !view) return;
      setCoverBusy(true);
      try {
        const dataUrl = await fileToResizedDataUrl(file);
        const updated = await setMasterSetCover(masterSetId, dataUrl, token);
        setView((v) => (v ? { ...v, master_set: updated } : v));
      } catch (e) {
        alert(e instanceof Error ? e.message : "Cover upload failed");
      } finally {
        setCoverBusy(false);
      }
    },
    [masterSetId, view],
  );

  const handleClearCover = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    setCoverBusy(true);
    try {
      const updated = await clearMasterSetCover(masterSetId, token);
      setView((v) => (v ? { ...v, master_set: updated } : v));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Remove failed");
    } finally {
      setCoverBusy(false);
    }
  }, [masterSetId]);

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
      <main className="mx-auto max-w-[100rem] px-6 py-10">
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

  return (
    <main className="mx-auto max-w-[100rem] px-6 py-10">
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
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowShare(true)}
            title="Public read-only share link"
            className={
              "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors " +
              (view.master_set.share_token
                ? "border-accent-green/40 bg-accent-green/10 text-accent-green"
                : "border-border bg-bg-surface text-text-secondary hover:border-accent-yellow/40 hover:text-accent-yellow")
            }
          >
            <span aria-hidden>🔗</span>
            {view.master_set.share_token ? "Sharing" : "Share"}
          </button>
          <Link
            href={`/sets/${view.master_set.set_id}`}
            className="text-xs text-text-secondary hover:text-text-primary underline decoration-dotted"
          >
            Browse full set →
          </Link>
        </div>
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

      {view.slots.length === 0 ? (
        <div className="rounded-card border border-dashed border-border bg-bg-surface p-8 text-center text-sm text-text-secondary">
          This set has no cards catalogued yet.
        </div>
      ) : (
        <BinderSpread
          slots={view.slots}
          gridSize={view.master_set.binder_size}
          setName={view.master_set.set_name}
          coverImageUrl={view.master_set.cover_image_url}
          isCompleted={!!view.master_set.completed_at}
          onUploadCover={handleUploadCover}
          onClearCover={handleClearCover}
          uploadBusy={coverBusy}
        />
      )}

      {celebrating && view && (
        <CompletionCelebration
          setName={view.master_set.set_name}
          onDismiss={() => setCelebrating(false)}
        />
      )}

      {showShare && (
        <MasterSetShareModal
          masterSetId={masterSetId}
          shareToken={view.master_set.share_token}
          onChange={(token) =>
            setView((v) =>
              v ? { ...v, master_set: { ...v.master_set, share_token: token } } : v,
            )
          }
          onClose={() => setShowShare(false)}
        />
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

