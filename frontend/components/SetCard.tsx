import Image from "next/image";
import Link from "next/link";

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

export function SetCard({ set }: Props) {
  const releaseLabel = formatReleaseDate(set.release_date);

  return (
    <Link
      href={`/sets/${set.id}`}
      className="group relative flex flex-col rounded-card bg-bg-surface border border-border p-4 transition-all duration-200 hover:border-accent-yellow/40 hover:shadow-md hover:shadow-accent-yellow/10 hover:-translate-y-0.5"
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

      <div className="h-16 w-full flex items-center justify-center mb-3">
        {set.logo_url ? (
          <Image
            src={set.logo_url}
            alt={set.name}
            width={160}
            height={64}
            className="max-h-16 w-auto object-contain group-hover:scale-[1.04] transition-transform duration-300"
            unoptimized
          />
        ) : (
          <span className="text-text-tertiary text-xs">no logo</span>
        )}
      </div>

      <div className="text-sm font-semibold truncate w-full text-center" title={set.name}>
        {set.name}
      </div>

      <div className="mt-2 flex items-center justify-center gap-2 text-xs font-mono text-text-tertiary">
        <span>{set.card_count}</span>
        <span className="opacity-50">·</span>
        {releaseLabel && <span>{releaseLabel}</span>}
      </div>
    </Link>
  );
}
