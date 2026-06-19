"use client";

import { useLanguage } from "./LanguageProvider";

/**
 * EN ↔ KR pill toggle that sits next to ThemeToggle in TopNav.
 * Persisted preference is stored client-side; server-rendered HTML
 * always says EN to avoid hydration mismatches and we swap on the
 * first client effect.
 */
export function LanguageToggle() {
  const { lang, setLang } = useLanguage();
  const next: typeof lang = lang === "en" ? "ko" : "en";
  return (
    <button
      type="button"
      onClick={() => setLang(next)}
      aria-label={`Switch language to ${next === "ko" ? "Korean" : "English"}`}
      title={`Switch to ${next.toUpperCase()}`}
      className="inline-flex h-8 min-w-[2rem] items-center justify-center gap-0.5 rounded-full border border-border px-2 text-[11px] font-mono font-semibold uppercase tracking-wider text-text-secondary transition-colors hover:text-text-primary hover:border-accent-yellow/40"
    >
      <span
        className={
          lang === "en"
            ? "text-text-primary"
            : "text-text-tertiary/60"
        }
      >
        EN
      </span>
      <span className="text-text-tertiary/40">/</span>
      <span
        className={
          lang === "ko"
            ? "text-text-primary"
            : "text-text-tertiary/60"
        }
      >
        KR
      </span>
    </button>
  );
}
