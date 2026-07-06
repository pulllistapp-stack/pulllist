"use client";

import { Copy, Link as LinkIcon, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { enableMasterSetShare, revokeMasterSetShare } from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Share modal for a master set — mint a public URL, copy it, or revoke.
 * Parent supplies the current share_token (null when not shared) plus a
 * callback that runs on every mint/revoke so the parent can keep its
 * MasterSet state in sync.
 */
export function MasterSetShareModal({
  masterSetId,
  shareToken,
  onChange,
  onClose,
}: {
  masterSetId: number;
  shareToken: string | null;
  onChange: (nextToken: string | null) => void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const shareUrl = shareToken
    ? typeof window !== "undefined"
      ? `${window.location.origin}/p/masters/${shareToken}`
      : `/p/masters/${shareToken}`
    : null;

  const mint = async () => {
    const token = getToken();
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      const m = await enableMasterSetShare(masterSetId, token);
      onChange(m.share_token);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    if (!confirm("Revoke share link? Anyone with the old URL will get a 404."))
      return;
    const token = getToken();
    if (!token) return;
    setBusy(true);
    setErr(null);
    try {
      const m = await revokeMasterSetShare(masterSetId, token);
      onChange(m.share_token);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/30 overflow-hidden"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-border">
          <div className="min-w-0">
            <p className="text-[10px] font-mono uppercase tracking-wider text-accent-yellow">
              Share master set
            </p>
            <h2 className="mt-0.5 text-lg font-bold text-text-primary">
              Public read-only link
            </h2>
            <p className="mt-1 text-xs text-text-secondary">
              Anyone with the URL sees your binder — cards owned + progress.
              No login required, no editing.
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 inline-flex h-8 w-8 items-center justify-center rounded-full text-text-tertiary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {shareUrl ? (
            <>
              <div className="rounded-2xl border border-border bg-bg p-3 flex items-center gap-2">
                <LinkIcon className="h-4 w-4 shrink-0 text-text-tertiary" />
                <input
                  readOnly
                  value={shareUrl}
                  className="flex-1 min-w-0 bg-transparent text-xs font-mono text-text-primary focus:outline-none"
                  onFocus={(e) => e.currentTarget.select()}
                />
                <button
                  type="button"
                  onClick={copy}
                  className="inline-flex items-center gap-1 rounded-full bg-accent-yellow text-gray-900 font-bold px-3 py-1.5 text-xs hover:brightness-105 transition-all shrink-0"
                >
                  <Copy className="h-3 w-3" />
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
              <button
                type="button"
                onClick={revoke}
                disabled={busy}
                className="w-full inline-flex items-center justify-center gap-1 rounded-full border border-border text-text-secondary font-semibold px-3 py-2 text-xs hover:text-accent-red hover:border-accent-red/40 transition-colors disabled:opacity-50"
              >
                {busy && <Loader2 className="h-3 w-3 animate-spin" />}
                Revoke share link
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={mint}
              disabled={busy}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-full bg-accent-yellow text-gray-900 font-bold px-4 py-2.5 text-sm hover:brightness-105 transition-all disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LinkIcon className="h-4 w-4" />
              )}
              Create share link
            </button>
          )}

          {err && (
            <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-xs text-accent-red">
              {err}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
