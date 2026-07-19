import Link from "next/link";

import type { CatalogRegion } from "@/lib/api";

type RegionDef = {
  code: CatalogRegion;
  flag: string;
  label: string;
  /** Tooltip for the "Coming soon" state. */
  comingSoon?: string;
};

export const REGIONS: RegionDef[] = [
  { code: "en", flag: "🇺🇸", label: "USA" },
  { code: "ja", flag: "🇯🇵", label: "Japan" },
  { code: "ko", flag: "🇰🇷", label: "Korea" },
  { code: "zh-cn", flag: "🇨🇳", label: "China (Simplified)" },
  { code: "zh-tw", flag: "🇹🇼", label: "Taiwan (Traditional)" },
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
      className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface p-1"
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
            title={r.comingSoon}
            className={[
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold transition-colors",
              isActive
                ? "bg-accent-yellow text-gray-900 shadow-sm"
                : "text-text-secondary hover:text-text-primary",
            ].join(" ")}
          >
            <span aria-hidden>{r.flag}</span>
            <span>{r.label}</span>
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
