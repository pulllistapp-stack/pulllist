"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  Check,
  ExternalLink,
  Flag,
  Loader2,
  RotateCcw,
  Tag,
  Image as ImageIcon,
  Type as TypeIcon,
} from "lucide-react";

import { AdminGuard } from "@/components/admin/AdminGuard";
import {
  listCardReports,
  listSetReports,
  updateCardReport,
  updateSetReport,
  type CardReportRow,
  type CardReportStatus,
  type SetReportRow,
  type SetReportStatus,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

type ReportScope = "card" | "set";

export default function AdminReportsPage() {
  return (
    <AdminGuard>
      <AdminReportsContent />
    </AdminGuard>
  );
}

const STATUS_TABS: { value: CardReportStatus | "all"; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "wontfix", label: "Won't fix" },
  { value: "all", label: "All" },
];

const CATEGORY_META: Record<
  string,
  { label: string; icon: typeof Tag; color: string }
> = {
  wrong_price: { label: "Wrong price", icon: Tag, color: "text-accent-yellow" },
  wrong_image: {
    label: "Wrong image",
    icon: ImageIcon,
    color: "text-teal-500",
  },
  wrong_name: { label: "Wrong name", icon: TypeIcon, color: "text-accent-green" },
  other: { label: "Other", icon: Flag, color: "text-text-secondary" },
};

const SET_CATEGORY_META: Record<
  string,
  { label: string; icon: typeof Tag; color: string }
> = {
  missing_cards: {
    label: "Missing cards",
    icon: Flag,
    color: "text-accent-yellow",
  },
  wrong_images: {
    label: "Wrong images",
    icon: ImageIcon,
    color: "text-teal-500",
  },
  wrong_metadata: {
    label: "Wrong info",
    icon: TypeIcon,
    color: "text-accent-green",
  },
  other: { label: "Other", icon: Flag, color: "text-text-secondary" },
};

function AdminReportsContent() {
  const [scope, setScope] = useState<ReportScope>("card");
  const [statusFilter, setStatusFilter] = useState<CardReportStatus | "all">(
    "open",
  );
  const [cardReports, setCardReports] = useState<CardReportRow[]>([]);
  const [setReports, setSetReports] = useState<SetReportRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (scope === "card") {
        const r = await listCardReports({
          status: statusFilter,
          pageSize: 100,
        });
        setCardReports(r.items);
        setTotal(r.total);
      } else {
        const r = await listSetReports({
          status: statusFilter as SetReportStatus | "all",
          pageSize: 100,
        });
        setSetReports(r.items);
        setTotal(r.total);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [scope, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const onResolveCard = async (
    reportId: number,
    next: CardReportStatus,
    note?: string,
  ) => {
    setBusy(reportId);
    try {
      const updated = await updateCardReport(reportId, {
        status: next,
        resolution_note: note ?? null,
      });
      setCardReports((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  const onResolveSet = async (
    reportId: number,
    next: SetReportStatus,
    note?: string,
  ) => {
    setBusy(reportId);
    try {
      const updated = await updateSetReport(reportId, {
        status: next,
        resolution_note: note ?? null,
      });
      setSetReports((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  const activeReports = scope === "card" ? cardReports : setReports;

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-text-primary">
          Reports
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          User-submitted data-quality issues. Toggle between card-level and
          set-level scopes; triage by category, leave a resolution note when
          closing.
        </p>
      </div>

      {/* Scope toggle + Status tabs — wrap onto two rows on narrow
          screens so neither pill group pushes past the viewport. */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
      <div className="inline-flex gap-1 rounded-full border border-border bg-bg-surface p-1">
        {(["card", "set"] as ReportScope[]).map((s) => {
          const active = scope === s;
          return (
            <button
              key={s}
              onClick={() => setScope(s)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider transition-colors",
                active
                  ? "bg-accent-red text-white"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {s === "card" ? "Card reports" : "Set reports"}
            </button>
          );
        })}
      </div>

      <div className="inline-flex gap-1 rounded-full border border-border bg-bg-surface p-1">
        {STATUS_TABS.map((tab) => {
          const active = statusFilter === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider transition-colors",
                active
                  ? "bg-accent-yellow text-gray-900"
                  : "text-text-secondary hover:text-text-primary",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12 text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : activeReports.length === 0 ? (
        <div className="rounded-card border border-border bg-bg-surface p-10 text-center">
          <Flag className="mx-auto h-8 w-8 text-text-tertiary" />
          <p className="mt-3 text-sm text-text-secondary">
            No {statusFilter === "all" ? "" : statusFilter}{" "}
            {scope === "card" ? "card" : "set"} reports.
          </p>
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs font-mono text-text-tertiary">
            {total} total · showing {activeReports.length}
          </p>
          <ul className="space-y-3">
            {scope === "card"
              ? cardReports.map((r) => (
                  <ReportRow
                    key={r.id}
                    report={r}
                    busy={busy === r.id}
                    onResolve={onResolveCard}
                  />
                ))
              : setReports.map((r) => (
                  <SetReportRowView
                    key={r.id}
                    report={r}
                    busy={busy === r.id}
                    onResolve={onResolveSet}
                  />
                ))}
          </ul>
        </>
      )}
    </main>
  );
}

function ReportRow({
  report,
  busy,
  onResolve,
}: {
  report: CardReportRow;
  busy: boolean;
  onResolve: (
    id: number,
    next: CardReportStatus,
    note?: string,
  ) => Promise<void>;
}) {
  const meta = CATEGORY_META[report.category] ?? CATEGORY_META.other;
  const Icon = meta.icon;
  const [note, setNote] = useState("");
  const isOpen = report.status === "open";

  const reporterLabel = report.reporter
    ? report.reporter.name ?? report.reporter.email
    : "anonymous";

  const ts = new Date(report.created_at);
  const relative = formatRelative(ts);

  return (
    <li className="rounded-2xl border border-border bg-bg-surface p-4">
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Card thumbnail */}
        {report.card_image_small ? (
          <Link
            href={`/cards/${report.card_id}`}
            className="shrink-0 w-16 h-22 rounded-md overflow-hidden bg-bg-elevated"
            title="Open card detail"
          >
            <Image
              src={report.card_image_small}
              alt=""
              width={64}
              height={88}
              className="object-cover w-full h-full"
              unoptimized
            />
          </Link>
        ) : (
          <div className="shrink-0 w-16 h-22 rounded-md bg-bg-elevated" />
        )}

        {/* Body */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <Link
              href={`/cards/${report.card_id}`}
              className="text-sm font-bold text-text-primary hover:text-accent-yellow transition-colors inline-flex items-center gap-1"
            >
              {report.card_name ?? report.card_id}
              <ExternalLink className="h-3 w-3 opacity-60" />
            </Link>
            <span className="text-xs text-text-tertiary font-mono">
              {report.set_name ?? "—"} · #{report.card_number ?? "?"}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border border-border bg-bg px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider",
                meta.color,
              )}
            >
              <Icon className="h-3 w-3" />
              {meta.label}
            </span>
            <span className="text-[11px] font-mono text-text-tertiary">
              by {reporterLabel} · {relative}
            </span>
            <StatusPill status={report.status} />
          </div>

          {report.comment && (
            <p className="mt-2 text-sm text-text-secondary italic leading-snug">
              &ldquo;{report.comment}&rdquo;
            </p>
          )}

          {report.resolution_note && !isOpen && (
            <div className="mt-2 rounded-card bg-bg/60 border border-border px-3 py-2 text-xs">
              <span className="text-text-tertiary font-mono uppercase tracking-wider">
                Resolved by{" "}
                {report.resolver?.name ?? report.resolver?.email ?? "admin"}
                :{" "}
              </span>
              <span className="text-text-secondary">{report.resolution_note}</span>
            </div>
          )}

          {/* Actions */}
          {isOpen ? (
            <div className="mt-3 flex flex-col sm:flex-row gap-2 sm:items-center">
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Resolution note (optional)"
                className="flex-1 rounded-full bg-bg border border-border px-3 py-1.5 text-xs focus:outline-none focus:border-accent-yellow/60 transition-colors"
                maxLength={500}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onResolve(report.id, "resolved", note || undefined)}
                  className="inline-flex items-center gap-1 rounded-full bg-accent-green text-white font-bold px-3 py-1.5 text-xs hover:brightness-110 transition-all disabled:opacity-50"
                >
                  {busy ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Check className="h-3 w-3" />
                  )}
                  Resolve
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => onResolve(report.id, "wontfix", note || undefined)}
                  className="inline-flex items-center gap-1 rounded-full border border-border text-text-secondary font-bold px-3 py-1.5 text-xs hover:text-text-primary hover:border-accent-red/40 transition-colors disabled:opacity-50"
                >
                  Won&apos;t fix
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => onResolve(report.id, "open")}
                className="inline-flex items-center gap-1 rounded-full border border-border text-text-secondary font-bold px-3 py-1.5 text-xs hover:text-text-primary transition-colors disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" />
                Re-open
              </button>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

/**
 * Same visual shape as ReportRow but keyed off a whole set instead of a
 * single card. Left side shows the set logo (fallback to a blank card
 * silhouette); the body renders category + reporter + comment identically
 * so the admin's eye can scan card and set reports side-by-side without
 * re-parsing the layout.
 */
function SetReportRowView({
  report,
  busy,
  onResolve,
}: {
  report: SetReportRow;
  busy: boolean;
  onResolve: (
    id: number,
    next: SetReportStatus,
    note?: string,
  ) => Promise<void>;
}) {
  const meta = SET_CATEGORY_META[report.category] ?? SET_CATEGORY_META.other;
  const Icon = meta.icon;
  const [note, setNote] = useState("");
  const isOpen = report.status === "open";

  const reporterLabel = report.reporter
    ? report.reporter.name ?? report.reporter.email
    : "anonymous";

  const ts = new Date(report.created_at);
  const relative = formatRelative(ts);

  return (
    <li className="rounded-2xl border border-border bg-bg-surface p-4">
      <div className="flex flex-col sm:flex-row gap-4">
        {report.set_logo_url ? (
          <Link
            href={`/sets/${report.set_id}`}
            className="shrink-0 w-24 h-16 rounded-md overflow-hidden bg-bg-elevated flex items-center justify-center"
            title="Open set"
          >
            <Image
              src={report.set_logo_url}
              alt=""
              width={96}
              height={64}
              className="max-h-16 w-auto object-contain"
              unoptimized
            />
          </Link>
        ) : (
          <div className="shrink-0 w-24 h-16 rounded-md bg-bg-elevated" />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <Link
              href={`/sets/${report.set_id}`}
              className="text-sm font-bold text-text-primary hover:text-accent-yellow transition-colors inline-flex items-center gap-1"
            >
              {report.set_name ?? report.set_id}
              <ExternalLink className="h-3 w-3 opacity-60" />
            </Link>
            <span className="text-xs text-text-tertiary font-mono">
              {report.set_id}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border border-border bg-bg px-2 py-0.5 text-[11px] font-mono uppercase tracking-wider",
                meta.color,
              )}
            >
              <Icon className="h-3 w-3" />
              {meta.label}
            </span>
            <span className="text-[11px] font-mono text-text-tertiary">
              by {reporterLabel} · {relative}
            </span>
            <StatusPill status={report.status} />
          </div>

          {report.comment && (
            <p className="mt-2 text-sm text-text-secondary italic leading-snug">
              &ldquo;{report.comment}&rdquo;
            </p>
          )}

          {report.resolution_note && !isOpen && (
            <div className="mt-2 rounded-card bg-bg/60 border border-border px-3 py-2 text-xs">
              <span className="text-text-tertiary font-mono uppercase tracking-wider">
                Resolved by{" "}
                {report.resolver?.name ?? report.resolver?.email ?? "admin"}:{" "}
              </span>
              <span className="text-text-secondary">
                {report.resolution_note}
              </span>
            </div>
          )}

          {isOpen ? (
            <div className="mt-3 flex flex-col sm:flex-row gap-2 sm:items-center">
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Resolution note (optional)"
                className="flex-1 rounded-full bg-bg border border-border px-3 py-1.5 text-xs focus:outline-none focus:border-accent-yellow/60 transition-colors"
                maxLength={500}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    onResolve(report.id, "resolved", note || undefined)
                  }
                  className="inline-flex items-center gap-1 rounded-full bg-accent-green text-white font-bold px-3 py-1.5 text-xs hover:brightness-110 transition-all disabled:opacity-50"
                >
                  {busy ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Check className="h-3 w-3" />
                  )}
                  Resolve
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    onResolve(report.id, "wontfix", note || undefined)
                  }
                  className="inline-flex items-center gap-1 rounded-full border border-border text-text-secondary font-bold px-3 py-1.5 text-xs hover:text-text-primary hover:border-accent-red/40 transition-colors disabled:opacity-50"
                >
                  Won&apos;t fix
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => onResolve(report.id, "open")}
                className="inline-flex items-center gap-1 rounded-full border border-border text-text-secondary font-bold px-3 py-1.5 text-xs hover:text-text-primary transition-colors disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" />
                Re-open
              </button>
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

function StatusPill({ status }: { status: CardReportStatus | SetReportStatus }) {
  const map: Record<CardReportStatus, { label: string; cls: string }> = {
    open: { label: "Open", cls: "bg-accent-yellow/15 text-accent-yellow border-accent-yellow/30" },
    resolved: { label: "Resolved", cls: "bg-accent-green/15 text-accent-green border-accent-green/30" },
    wontfix: { label: "Won't fix", cls: "bg-bg border-border text-text-tertiary" },
  };
  const m = map[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider font-bold",
        m.cls,
      )}
    >
      {m.label}
    </span>
  );
}

function formatRelative(d: Date): string {
  const diffMs = Date.now() - d.getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  return d.toLocaleDateString();
}
