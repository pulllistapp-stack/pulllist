"use client";

import Image from "next/image";
import Link from "next/link";

import { useLanguage } from "@/components/LanguageProvider";
import type { SetWithCardCount } from "@/lib/api";

type Props = {
  set: SetWithCardCount;
};

function formatReleaseDate(d: string | null): string | null {
  if (!d) return null;
  const parts = d.split("-");
  if (parts.length < 2) return d;
  const year = parts[0];
  const monthNum = parseInt(parts[1], 10);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[monthNum - 1] ?? ""} ${year}`;
}

function fmtValue(v: number | null): string | null {
  if (v == null || v <= 0) return null;
  if (v >= 10000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 1000) return `$${(v / 1000).toFixed(2)}k`;
  return `$${v.toFixed(0)}`;
}

export function SetCard({ set }: Props) {
  const { setName } = useLanguage();
  const displayName = setName(set);
  const releaseLabel = formatReleaseDate(set.release_date);
  const valueLabel = fmtValue(set.total_value_usd);
  const progress = set.owned_unique != null && set.card_count > 0
    ? (set.owned_unique / set.card_count) * 100
    : null;

  return (
    <Link
      href={`/sets/${set.id}`}
      className="group relative flex flex-col rounded-card bg-bg-surface border border-border p-4 transition-all duration-200 hover:border-accent-yellow/60 hover:shadow-lg hover:shadow-accent-yellow/20 hover:-translate-y-1 active:translate-y-0"
    >
      {set.symbol_url && (
        <div className="absolute right-3 top-3 h-5 w-5 opacity-60 group-hover:opacity-100 transition-opacity">
          <Image
            src={set.symbol_url}
            alt=""
            width={20}
            height={20}
            className="object-contain"
            unoptimized
          />
        </div>
      )}

      <div className="relative h-16 w-full flex items-center justify-center mb-3">
        {set.logo_url ? (
          <Image
            src={set.logo_url}
            alt={displayName}
            width={160}
            height={64}
            className="max-h-16 w-auto object-contain group-hover:scale-[1.04] transition-transform duration-300"
            unoptimized
          />
        ) : (
          // Pretty placeholder for sets without a logo - common for JP imports
          // where TCGdex returns logo: null. Better than the bare "no logo"
          // text; renders the set name in a styled card so the grid still has
          // visual weight.
          <div className="h-full w-full flex items-center justify-center rounded-md bg-gradient-to-br from-bg/60 to-accent-yellow/[0.08] dark:from-bg/40 dark:to-accent-yellow/10 border border-dashed border-border/60 px-3 group-hover:border-accent-yellow/40 group-hover:scale-[1.02] transition-all duration-300">
            <span
              className="font-bold text-sm text-text-primary/80 text-center leading-tight line-clamp-2"
              title={displayName}
            >
              {displayName}
            </span>
          </div>
        )}
      </div>

      <div className="text-sm font-semibold w-full text-center leading-tight" title={displayName}>
        <div className="truncate">{displayName}</div>
        {/* English name in muted parens for JP-primary sets - matches the
            card-binder convention "クレイバースト (Clay Burst)". Skip when
            the English name is identical (avoids "Wild Force (Wild Force)"). */}
        {set.name_en && set.name_en !== displayName && (
          <div className="mt-0.5 text-xs font-normal text-text-tertiary truncate">
            ({set.name_en})
          </div>
        )}
      </div>

      <div className="mt-2 flex items-center justify-center gap-2 text-xs font-mono text-text-tertiary">
        <span>{set.card_count} cards</span>
        {releaseLabel && (
          <>
            <span className="opacity-50">·</span>
            <span>{releaseLabel}</span>
          </>
        )}
      </div>

      {progress != null && (
        <div className="mt-3 px-1">
          <div className="flex items-baseline justify-between text-xs font-mono mb-1">
            <span className="uppercase tracking-wider text-text-tertiary">Collected</span>
            <span className="text-accent-green font-semibold">
              {set.owned_unique}/{set.card_count}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg/60">
            <div
              className="h-full rounded-full bg-accent-green transition-all"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        </div>
      )}

      {valueLabel && (
        <div className="mt-3 flex items-center justify-between text-xs px-1">
          <span className="font-mono uppercase tracking-wider text-text-tertiary">
            Set value
          </span>
          <span className="font-mono font-bold text-accent-yellow">{valueLabel}</span>
        </div>
      )}
    </Link>
  );
}
