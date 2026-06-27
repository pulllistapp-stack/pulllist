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
  updateCardReport,
  type CardReportRow,
  type CardReportStatus,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

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

function AdminReportsContent() {
  const [statusFilter, setStatusFilter] = useState<CardReportStatus | "all">(
    "open",
  );
  const [reports, setReports] = useState<CardReportRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await listCardReports({
        status: statusFilter,
        pageSize: 100,
      });
      setReports(r.items);
      setTotal(r.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const onResolve = async (
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
      // optimistic local replace, then refetch to honour the active filter
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      await load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-text-primary">
          Card reports
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          User-submitted data-quality issues. Triage by category, leave a
          resolution note when closing.
        </p>
      </div>

      {/* Status tabs */}
      <div className="mb-5 inline-flex gap-1 rounded-full border border-border bg-bg-surface p-1">
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

      {loading ? (
        <div className="flex items-center justify-center py-12 text-text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-card border border-border bg-bg-surface p-10 text-center">
          <Flag className="mx-auto h-8 w-8 text-text-tertiary" />
          <p className="mt-3 text-sm text-text-secondary">
            No {statusFilter === "all" ? "" : statusFilter} reports.
          </p>
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs font-mono text-text-tertiary">
            {total} total · showing {reports.length}
          </p>
          <ul className="space-y-3">
            {reports.map((r) => (
              <ReportRow
                key={r.id}
                report={r}
                busy={busy === r.id}
                onResolve={onResolve}
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

function StatusPill({ status }: { status: CardReportStatus }) {
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
