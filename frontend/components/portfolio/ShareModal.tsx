"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  Eye,
  EyeOff,
  Globe,
  Loader2,
  Lock,
  RefreshCw,
  Share2,
  X,
} from "lucide-react";

import {
  getMySharing,
  rotateShareToken,
  updateMySharing,
  type SharingSettings,
} from "@/lib/auth";
import { cn } from "@/lib/utils";

type Props = {
  onClose: () => void;
};

/**
 * Settings modal for "Share my portfolio" on /portfolio. Manages the public
 * toggle, bio, per-section visibility toggles, and the share URL with copy
 * + rotate. Token rotation invalidates any old shared link.
 */
export function ShareModal({ onClose }: Props) {
  const [settings, setSettings] = useState<SharingSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMySharing()
      .then((s) => {
        if (!cancelled) setSettings(s);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Load failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const patch = async (changes: Partial<SharingSettings>) => {
    setSaving(Object.keys(changes)[0] ?? "patch");
    setErr(null);
    try {
      const updated = await updateMySharing(changes);
      setSettings(updated);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(null);
    }
  };

  const onRotate = async () => {
    if (
      !confirm(
        "Rotate the share URL? Anyone with your old link will lose access.",
      )
    )
      return;
    setSaving("rotate");
    setErr(null);
    try {
      const updated = await rotateShareToken();
      setSettings(updated);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Rotate failed");
    } finally {
      setSaving(null);
    }
  };

  const fullUrl =
    settings?.share_url && typeof window !== "undefined"
      ? `${window.location.origin}${settings.share_url}`
      : "";

  const onCopy = () => {
    if (!fullUrl) return;
    navigator.clipboard.writeText(fullUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-3xl border border-border bg-bg-surface shadow-2xl shadow-black/20"
      >
        {/* Header */}
        <div className="sticky top-0 bg-bg-surface flex items-center justify-between gap-3 px-5 py-4 border-b border-border z-10">
          <div className="flex items-center gap-2">
            <Share2 className="h-5 w-5 text-accent-yellow" />
            <h2 className="text-lg font-bold text-text-primary">
              Share your portfolio
            </h2>
          </div>
          <button
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-text-tertiary hover:text-text-primary hover:bg-bg-elevated transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          {loading && (
            <div className="flex items-center justify-center py-12 text-text-tertiary">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          )}

          {settings && (
            <>
              {/* Master toggle */}
              <div
                className={cn(
                  "rounded-2xl border p-4 transition-colors",
                  settings.is_public
                    ? "border-accent-green/40 bg-accent-green/5"
                    : "border-border bg-bg/40",
                )}
              >
                <label className="flex items-start justify-between gap-3 cursor-pointer">
                  <div className="flex items-start gap-3 min-w-0">
                    <span
                      className={cn(
                        "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                        settings.is_public
                          ? "bg-accent-green/15 text-accent-green"
                          : "bg-bg-elevated text-text-tertiary",
                      )}
                    >
                      {settings.is_public ? (
                        <Globe className="h-5 w-5" />
                      ) : (
                        <Lock className="h-5 w-5" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="font-bold text-text-primary">
                        {settings.is_public
                          ? "Public — anyone with the link can view"
                          : "Private — only you can view"}
                      </p>
                      <p className="text-xs text-text-secondary mt-0.5">
                        {settings.is_public
                          ? "Your portfolio is shareable. Toggle off to lock it down."
                          : "Toggle on to generate a non-guessable share link."}
                      </p>
                    </div>
                  </div>
                  <Toggle
                    checked={settings.is_public}
                    onChange={(v) => patch({ is_public: v })}
                    busy={saving === "is_public"}
                  />
                </label>
              </div>

              {settings.is_public && (
                <>
                  {/* Share URL */}
                  <section>
                    <h3 className="mb-2 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
                      Your share link
                    </h3>
                    <div className="flex gap-2">
                      <input
                        readOnly
                        value={fullUrl}
                        onClick={(e) => e.currentTarget.select()}
                        className="flex-1 rounded-full bg-bg border border-border px-3 py-2 text-xs font-mono text-text-primary focus:outline-none focus:border-accent-yellow/60 selection:bg-accent-yellow/30"
                      />
                      <button
                        onClick={onCopy}
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-bold transition-colors shrink-0",
                          copied
                            ? "bg-accent-green text-white"
                            : "bg-accent-yellow text-gray-900 hover:brightness-105",
                        )}
                      >
                        {copied ? (
                          <>
                            <Check className="h-3.5 w-3.5" /> Copied
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" /> Copy
                          </>
                        )}
                      </button>
                    </div>
                    <button
                      onClick={onRotate}
                      disabled={saving === "rotate"}
                      className="mt-2 inline-flex items-center gap-1 text-[11px] text-text-tertiary hover:text-text-primary transition-colors disabled:opacity-50"
                    >
                      {saving === "rotate" ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <RefreshCw className="h-3 w-3" />
                      )}
                      Rotate URL (invalidates the old link)
                    </button>
                  </section>

                  {/* Bio */}
                  <section>
                    <h3 className="mb-2 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
                      Bio <span className="lowercase">(optional, 160 chars)</span>
                    </h3>
                    <textarea
                      defaultValue={settings.bio ?? ""}
                      onBlur={(e) => {
                        const next = e.target.value.trim() || null;
                        if (next !== settings.bio) patch({ bio: next });
                      }}
                      rows={2}
                      maxLength={160}
                      placeholder="e.g. Chasing Charizards since 1999. Master Set hunter."
                      className="w-full rounded-2xl bg-bg border border-border px-3 py-2 text-sm focus:outline-none focus:border-accent-yellow/60 focus:ring-2 focus:ring-accent-yellow/15 transition-colors resize-none"
                    />
                  </section>

                  {/* Per-section toggles */}
                  <section className="space-y-2">
                    <h3 className="mb-1 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
                      What to share
                    </h3>
                    <ToggleRow
                      label="Total collection value ($)"
                      sub="Recommended on — viewers see what your vault is worth"
                      checked={settings.show_value}
                      busy={saving === "show_value"}
                      onChange={(v) => patch({ show_value: v })}
                    />
                    <ToggleRow
                      label="Growth chart (value over time)"
                      sub="Off by default — your private metric"
                      checked={settings.show_growth}
                      busy={saving === "show_growth"}
                      onChange={(v) => patch({ show_growth: v })}
                    />
                    <ToggleRow
                      label="Wishlist"
                      sub="Off by default — viewers see your target cards"
                      checked={settings.show_wishlist}
                      busy={saving === "show_wishlist"}
                      onChange={(v) => patch({ show_wishlist: v })}
                    />
                    <ToggleRow
                      label="Entire card grid"
                      sub="Off by default — only Top 20 shown. Toggle to expose the full vault."
                      checked={settings.show_all_cards}
                      busy={saving === "show_all_cards"}
                      onChange={(v) => patch({ show_all_cards: v })}
                    />
                  </section>

                  {/* Privacy note */}
                  <p className="text-[11px] text-text-tertiary leading-relaxed border-t border-border pt-3">
                    <Lock className="inline h-3 w-3 mr-1" />
                    Your email and real name are never exposed. Anyone with the
                    link can see only what you toggle on above. Rotate the URL
                    anytime to revoke access.
                  </p>
                </>
              )}

              {err && (
                <div className="rounded-card bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
                  {err}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  busy,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  busy?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={busy}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        "disabled:opacity-60",
        checked ? "bg-accent-green" : "bg-bg-elevated",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

function ToggleRow({
  label,
  sub,
  checked,
  onChange,
  busy,
}: {
  label: string;
  sub: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  busy?: boolean;
}) {
  return (
    <label className="flex items-start justify-between gap-3 rounded-xl border border-border/70 bg-bg/40 p-3 cursor-pointer hover:border-accent-yellow/30 transition-colors">
      <div className="flex items-start gap-2 min-w-0">
        {checked ? (
          <Eye className="mt-0.5 h-4 w-4 shrink-0 text-accent-green" />
        ) : (
          <EyeOff className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" />
        )}
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text-primary">{label}</p>
          <p className="text-[11px] text-text-tertiary leading-snug">{sub}</p>
        </div>
      </div>
      <Toggle checked={checked} onChange={onChange} busy={busy} />
    </label>
  );
}
