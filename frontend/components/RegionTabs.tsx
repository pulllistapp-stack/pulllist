import Link from "next/link";

import type { CatalogRegion } from "@/lib/api";

type RegionDef = {
  code: CatalogRegion;
  flag: string;
  label: string;
  /** Compact code shown on mobile — full label is too wide for
   *  five tabs to fit a phone viewport comfortably. */
  short: string;
  /** Tooltip for the "Coming soon" state. */
  comingSoon?: string;
};

export const REGIONS: RegionDef[] = [
  { code: "en", flag: "🇺🇸", label: "USA", short: "EN" },
  { code: "ja", flag: "🇯🇵", label: "Japan", short: "JP" },
  { code: "ko", flag: "🇰🇷", label: "Korea", short: "KR" },
  { code: "zh-cn", flag: "🇨🇳", label: "China (Simplified)", short: "CN" },
  { code: "zh-tw", flag: "🇹🇼", label: "Taiwan (Traditional)", short: "TW" },
];

type Props = {
  active: CatalogRegion;
  /** Path prefix the tab links to (e.g. "/sets"). */
  hrefBase: string;
};

/**
 * Server-component-safe region selector. Each tab is a real <Link>
 * so the URL (?region=...) is the source of truth — bookmarks, share
 * URLs, and back/forward all work. Active state is purely visual; the
 * server reads `searchParams.region` and renders the right catalog.
 */
export function RegionTabs({ active, hrefBase }: Props) {
  return (
    <div
      role="tablist"
      aria-label="Catalog region"
      className="inline-flex max-w-full items-center gap-0.5 sm:gap-1 rounded-full border border-border bg-bg-surface p-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {REGIONS.map((r) => {
        const isActive = r.code === active;
        const href = `${hrefBase}?region=${r.code}`;
        return (
          <Link
            key={r.code}
            href={href}
            role="tab"
            aria-selected={isActive}
            title={r.label}
            className={[
              "inline-flex shrink-0 items-center gap-1 sm:gap-1.5 rounded-full px-2.5 sm:px-3 py-1.5 text-sm font-semibold transition-colors",
              isActive
                ? "bg-accent-yellow text-gray-900 shadow-sm"
                : "text-text-secondary hover:text-text-primary",
            ].join(" ")}
          >
            <span aria-hidden>{r.flag}</span>
            {/* Mobile shows compact 2-letter code, desktop keeps the
                full country name so the tab bar reads naturally on
                a wider screen. */}
            <span className="sm:hidden">{r.short}</span>
            <span className="hidden sm:inline">{r.label}</span>
            {r.comingSoon && (
              <span className="ml-1 rounded-full bg-text-tertiary/15 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-text-tertiary font-mono">
                soon
              </span>
            )}
          </Link>
        );
      })}
    </div>
  );
}
