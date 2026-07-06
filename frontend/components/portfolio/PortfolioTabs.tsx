"use client";

import Link from "next/link";

type Tab = {
  href: string;
  label: string;
  hint?: string;
};

const TABS: Tab[] = [
  { href: "/portfolio", label: "Collection", hint: "Every card you own" },
  { href: "/portfolio/masters", label: "Master Sets", hint: "Set-completion binders" },
];

export function PortfolioTabs({ active }: { active: "collection" | "masters" }) {
  return (
    <div
      role="tablist"
      aria-label="Portfolio sections"
      className="mb-6 flex flex-wrap gap-1 border-b border-border"
    >
      {TABS.map((t) => {
        const isActive =
          (active === "collection" && t.href === "/portfolio") ||
          (active === "masters" && t.href === "/portfolio/masters");
        return (
          <Link
            key={t.href}
            href={t.href}
            role="tab"
            aria-selected={isActive}
            title={t.hint}
            className={
              "relative -mb-px inline-flex items-center gap-2 rounded-t-btn px-4 py-2.5 text-sm font-semibold transition-colors " +
              (isActive
                ? "border-b-2 border-accent-yellow text-text-primary"
                : "border-b-2 border-transparent text-text-secondary hover:text-text-primary")
            }
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}
