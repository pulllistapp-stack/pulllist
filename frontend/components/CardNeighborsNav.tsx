"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import type { CardNeighbors } from "@/lib/api";

type Props = {
  setId: string;
  setName: string | null;
  neighbors: CardNeighbors;
};

export function CardNeighborsNav({ setId, setName, neighbors }: Props) {
  const router = useRouter();
  const { prev, next, position, total } = neighbors;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.target instanceof HTMLTextAreaElement) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === "ArrowLeft" && prev) {
        e.preventDefault();
        router.push(`/cards/${prev.id}`);
      } else if (e.key === "ArrowRight" && next) {
        e.preventDefault();
        router.push(`/cards/${next.id}`);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prev, next, router]);

  return (
    <nav className="flex items-stretch justify-between gap-3 mb-6">
      <NeighborLink card={prev} side="prev" />
      <div className="hidden sm:flex flex-col items-center justify-center text-xs text-text-tertiary font-mono px-2">
        <Link
          href={`/sets/${setId}`}
          className="text-text-secondary hover:text-text-primary text-sm font-medium mb-0.5 truncate max-w-[200px]"
        >
          {setName ?? setId}
        </Link>
        {position != null && (
          <span>
            {position} / {total}
          </span>
        )}
        <span className="hidden md:block text-[10px] text-text-tertiary mt-1">
          ← → to navigate
        </span>
      </div>
      <NeighborLink card={next} side="next" />
    </nav>
  );
}

function NeighborLink({
  card,
  side,
}: {
  card: CardNeighbors["prev"];
  side: "prev" | "next";
}) {
  const isPrev = side === "prev";
  const align = isPrev ? "text-left" : "text-right";
  const justify = isPrev ? "justify-start" : "justify-end flex-row-reverse";

  if (!card) {
    return (
      <div
        className={`flex-1 rounded-card border border-border bg-bg-surface/40 p-3 text-text-tertiary text-xs flex items-center ${justify} opacity-50`}
      >
        <span>{isPrev ? "← Start of set" : "End of set →"}</span>
      </div>
    );
  }

  return (
    <Link
      href={`/cards/${card.id}`}
      className={`flex-1 rounded-card bg-bg-surface border border-border hover:border-accent-yellow/40 transition-colors p-3 flex items-center gap-3 ${justify}`}
    >
      <div className="relative w-10 h-14 flex-shrink-0">
        {card.image_small ? (
          <Image
            src={card.image_small}
            alt={card.name}
            fill
            sizes="40px"
            className="object-contain rounded-sm"
            unoptimized
          />
        ) : null}
      </div>
      <div className={`flex-1 min-w-0 ${align}`}>
        <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
          {isPrev ? "← Previous" : "Next →"}
        </div>
        <div className="text-sm font-medium truncate">{card.name}</div>
        <div className="text-xs font-mono text-text-tertiary">
          #{card.number ?? "—"}
        </div>
      </div>
    </Link>
  );
}
