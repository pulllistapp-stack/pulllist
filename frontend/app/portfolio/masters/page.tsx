"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { MascotLoader } from "@/components/MascotLoader";
import { MiniBinderCover } from "@/components/portfolio/MiniBinderCover";
import { PortfolioTabs } from "@/components/portfolio/PortfolioTabs";
import {
  BinderSize,
  MasterSet,
  MasterSetDisplayMode,
  SetWithCardCount,
  createMasterSet,
  deleteMasterSet,
  listMasterSets,
  listSets,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

export default function MasterSetsListPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [rows, setRows] = useState<MasterSet[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=/portfolio/masters");
      return;
    }
    const token = getToken();
    if (!token) return;
    (async () => {
      try {
        setRows(await listMasterSets(token));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
  }, [authLoading, user, router]);

  const handleCreated = (m: MasterSet) => {
    setRows((prev) => (prev ? [m, ...prev] : [m]));
    setShowCreate(false);
    router.push(`/portfolio/masters/${m.id}`);
  };

  const handleDelete = async (m: MasterSet) => {
    if (!confirm(`Remove master set "${m.set_name}"? Your collection is unaffected.`))
      return;
    const token = getToken();
    if (!token) return;
    setDeletingId(m.id);
    try {
      await deleteMasterSet(m.id, token);
      setRows((prev) => (prev ? prev.filter((x) => x.id !== m.id) : prev));
    } catch (e) {
      alert(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  if (authLoading || !user) {
    return (
      <main className="mx-auto max-w-7xl px-6 py-10">
        <MascotLoader size="lg" className="py-12" />
      </main>
    );
  }

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
        <span className="text-text-primary">Master Sets</span>
      </nav>

      <PortfolioTabs active="masters" />

      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold mb-1 tracking-tight">
            Master Sets
          </h1>
          <p className="text-text-secondary text-sm">
            Track set completion the way a binder does — one page per pocket.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-full bg-accent-yellow px-4 py-2.5 text-sm font-semibold text-bg hover:brightness-110"
        >
          <span aria-hidden>＋</span> New master set
        </button>
      </div>

      {error && (
        <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-4 text-sm mb-4">
          <div className="font-semibold mb-1">Failed to load</div>
          <div className="text-text-secondary font-mono">{error}</div>
        </div>
      )}

      {rows === null && <MascotLoader size="lg" className="py-12" />}

      {rows !== null && rows.length === 0 && !error && (
        <div className="rounded-card border border-dashed border-border bg-bg-surface p-10 text-center">
          <div className="text-5xl mb-3" aria-hidden>
            📖
          </div>
          <h2 className="text-lg font-semibold mb-1">
            No binders yet
          </h2>
          <p className="text-sm text-text-secondary mb-5">
            Pick a set and we&apos;ll lay out every card in a binder-style
            grid — colour for owned, silhouette for still-to-pull.
          </p>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 rounded-full bg-accent-yellow px-4 py-2.5 text-sm font-semibold text-bg hover:brightness-110"
          >
            <span aria-hidden>＋</span> Start your first master set
          </button>
        </div>
      )}

      {rows && rows.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((m) => (
            <MasterSetCard
              key={m.id}
              row={m}
              onDelete={() => handleDelete(m)}
              deleting={deletingId === m.id}
            />
          ))}
        </ul>
      )}

      {showCreate && (
        <CreateMasterSetModal
          existingSetIds={new Set(rows?.map((r) => r.set_id) ?? [])}
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
        />
      )}
    </main>
  );
}

function MasterSetCard({
  row,
  onDelete,
  deleting,
}: {
  row: MasterSet;
  onDelete: () => void;
  deleting: boolean;
}) {
  const basePct = row.total_base
    ? Math.round((row.owned_base / row.total_base) * 100)
    : 0;
  const masterPct = row.total_master
    ? Math.round((row.owned_master / row.total_master) * 100)
    : 0;
  return (
    <li className="rounded-card border border-border bg-bg-surface p-4 hover:border-accent-yellow/40 transition-colors">
      <Link href={`/portfolio/masters/${row.id}`} className="block">
        <div className="flex items-start gap-3 mb-3">
          <MiniBinderCover
            coverImageUrl={row.cover_image_url}
            className="h-16 w-12"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-0.5">
              {row.set_logo_url && (
                <Image
                  src={row.set_logo_url}
                  alt=""
                  width={44}
                  height={20}
                  className="max-h-5 w-auto object-contain shrink-0"
                  unoptimized
                />
              )}
              <div className="font-semibold truncate">{row.set_name}</div>
            </div>
            <div className="text-xs text-text-tertiary uppercase tracking-wider">
              {row.binder_size} binder ·{" "}
              {row.display_mode === "master" ? "Master view" : "Base view"}
            </div>
          </div>
        </div>

        <ProgressBar
          label="Base"
          owned={row.owned_base}
          total={row.total_base}
          pct={basePct}
        />
        <div className="h-2" />
        <ProgressBar
          label="Master"
          owned={row.owned_master}
          total={row.total_master}
          pct={masterPct}
          subtle
        />
      </Link>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onDelete}
          disabled={deleting}
          className="text-xs text-text-tertiary hover:text-accent-red disabled:opacity-50"
        >
          {deleting ? "Removing…" : "Remove"}
        </button>
      </div>
    </li>
  );
}

function ProgressBar({
  label,
  owned,
  total,
  pct,
  subtle,
}: {
  label: string;
  owned: number;
  total: number;
  pct: number;
  subtle?: boolean;
}) {
  const complete = pct === 100 && total > 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs mb-1">
        <span
          className={
            subtle ? "text-text-tertiary" : "text-text-secondary font-medium"
          }
        >
          {label}
        </span>
        <span className="font-mono tabular-nums text-text-secondary">
          {owned}/{total} · {pct}%
        </span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-bg overflow-hidden">
        <div
          className={
            "h-full transition-[width] duration-500 " +
            (complete
              ? "bg-accent-green"
              : subtle
                ? "bg-accent-yellow/50"
                : "bg-accent-yellow")
          }
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const BINDER_OPTIONS: {
  size: BinderSize;
  label: string;
  pockets: number;
}[] = [
  { size: "3x3", label: "3 × 3", pockets: 9 },
  { size: "4x3", label: "4 × 3", pockets: 12 },
  { size: "4x4", label: "4 × 4", pockets: 16 },
];

function CreateMasterSetModal({
  existingSetIds,
  onClose,
  onCreated,
}: {
  existingSetIds: Set<string>;
  onClose: () => void;
  onCreated: (m: MasterSet) => void;
}) {
  const [sets, setSets] = useState<SetWithCardCount[] | null>(null);
  const [q, setQ] = useState("");
  const [pickedSetId, setPickedSetId] = useState<string | null>(null);
  const [binder, setBinder] = useState<BinderSize>("3x3");
  const [mode, setMode] = useState<MasterSetDisplayMode>("base");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setSets(await listSets({ region: "en" }));
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Failed to load sets");
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    if (!sets) return [];
    const needle = q.trim().toLowerCase();
    return sets
      .filter(
        (s) =>
          !existingSetIds.has(s.id) &&
          (!needle ||
            s.name.toLowerCase().includes(needle) ||
            (s.series ?? "").toLowerCase().includes(needle) ||
            s.id.toLowerCase().includes(needle)),
      )
      .slice(0, 40);
  }, [sets, q, existingSetIds]);

  const submit = async () => {
    const token = getToken();
    if (!pickedSetId || !token) return;
    setBusy(true);
    setErr(null);
    try {
      const m = await createMasterSet(
        {
          set_id: pickedSetId,
          binder_size: binder,
          display_mode: mode,
          sort_mode: "number",
        },
        token,
      );
      onCreated(m);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Create failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl max-h-[90dvh] overflow-hidden rounded-card bg-bg-elevated border border-border shadow-xl flex flex-col">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <h2 className="font-bold text-lg">New master set</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-text-tertiary hover:text-text-primary text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-5 space-y-5 overflow-y-auto">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Set
            </label>
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search EN sets…"
              className="w-full rounded-btn bg-bg-surface border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/50"
            />
            <div className="mt-2 max-h-56 overflow-y-auto rounded-btn border border-border filter-scroll">
              {sets === null && (
                <div className="p-3 text-sm text-text-tertiary">
                  Loading sets…
                </div>
              )}
              {sets && filtered.length === 0 && (
                <div className="p-3 text-sm text-text-tertiary">
                  No sets match.{" "}
                  {existingSetIds.size > 0 &&
                    "Ones you already track are hidden."}
                </div>
              )}
              <ul>
                {filtered.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => setPickedSetId(s.id)}
                      className={
                        "w-full text-left px-3 py-2 text-sm border-b border-border last:border-b-0 flex items-center gap-3 " +
                        (pickedSetId === s.id
                          ? "bg-accent-yellow/10"
                          : "hover:bg-bg-surface")
                      }
                    >
                      {s.logo_url ? (
                        <div className="relative h-6 w-10 shrink-0 flex items-center justify-center">
                          <Image
                            src={s.logo_url}
                            alt=""
                            width={40}
                            height={24}
                            className="max-h-6 w-auto object-contain"
                            unoptimized
                          />
                        </div>
                      ) : (
                        <div className="h-6 w-10 shrink-0" aria-hidden />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="truncate">{s.name}</div>
                        <div className="text-xs text-text-tertiary">
                          {s.card_count} cards
                          {s.release_date && ` · ${s.release_date}`}
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Binder size
            </label>
            <div className="grid grid-cols-3 gap-2">
              {BINDER_OPTIONS.map((b) => {
                const active = binder === b.size;
                return (
                  <button
                    key={b.size}
                    type="button"
                    onClick={() => setBinder(b.size)}
                    className={
                      "rounded-btn border p-3 text-center transition-colors " +
                      (active
                        ? "border-accent-yellow bg-accent-yellow/10"
                        : "border-border bg-bg-surface hover:border-text-tertiary")
                    }
                  >
                    <BinderPreview size={b.size} active={active} />
                    <div className="mt-1 text-sm font-semibold">
                      {b.label}
                    </div>
                    <div className="text-xs text-text-tertiary">
                      {b.pockets} pkt
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-text-secondary">
              Default view
            </label>
            <div className="flex gap-2">
              {(["base", "master"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={
                    "flex-1 rounded-btn border py-2 text-sm font-medium transition-colors " +
                    (mode === m
                      ? "border-accent-yellow bg-accent-yellow/10 text-text-primary"
                      : "border-border bg-bg-surface text-text-secondary hover:text-text-primary")
                  }
                >
                  {m === "base"
                    ? "Base — one per card"
                    : "Master — every variant"}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-text-tertiary">
              You can flip between the two on the binder page any time.
            </p>
          </div>

          {err && (
            <div className="rounded-btn bg-accent-red/10 border border-accent-red/30 p-3 text-xs text-accent-red">
              {err}
            </div>
          )}
        </div>

        <div className="border-t border-border p-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-border px-4 py-2 text-sm hover:border-text-tertiary"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!pickedSetId || busy}
            className="rounded-full bg-accent-yellow px-4 py-2 text-sm font-semibold text-bg disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function BinderPreview({ size, active }: { size: BinderSize; active: boolean }) {
  const [cols, rows] = size.split("x").map(Number);
  const total = cols * rows;
  return (
    <div
      className="mx-auto grid gap-0.5"
      style={{
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        width: `${cols * 10 + (cols - 1) * 2}px`,
      }}
      aria-hidden
    >
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={
            "block h-2.5 rounded-[2px] " +
            (active ? "bg-accent-yellow" : "bg-text-tertiary/30")
          }
        />
      ))}
    </div>
  );
}
