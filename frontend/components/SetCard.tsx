import Image from "next/image";
import Link from "next/link";

import type { SetWithCardCount } from "@/lib/api";

type Props = {
  set: SetWithCardCount;
};

export function SetCard({ set }: Props) {
  return (
    <Link
      href={`/sets/${set.id}`}
      className="group rounded-card bg-bg-surface border border-border p-4 hover:border-accent-yellow/40 transition-colors flex flex-col items-center text-center"
    >
      {set.logo_url ? (
        <div className="h-16 w-full flex items-center justify-center mb-3">
          <Image
            src={set.logo_url}
            alt={set.name}
            width={160}
            height={64}
            className="max-h-16 w-auto object-contain group-hover:scale-[1.03] transition-transform"
            unoptimized
          />
        </div>
      ) : (
        <div className="h-16 mb-3 flex items-center justify-center text-text-tertiary text-xs">
          no logo
        </div>
      )}
      <div className="text-sm font-medium truncate w-full" title={set.name}>
        {set.name}
      </div>
      <div className="text-xs text-text-tertiary font-mono mt-1">
        {set.card_count} cards
      </div>
    </Link>
  );
}
