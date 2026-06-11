"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { Suggestion } from "@/lib/api";
import { suggestCards } from "@/lib/api";

export function SearchBar({ compact = false }: { compact?: boolean }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);

  useEffect(() => {
    if (q.trim().length < 2) {
      setItems([]);
      return;
    }

    let cancelled = false;
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await suggestCards(q.trim(), 8);
        if (!cancelled) setItems(res);
      } catch {
        if (!cancelled) setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 150);

    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const submit = (term: string) => {
    if (!term.trim()) return;
    setOpen(false);
    router.push(`/search?q=${encodeURIComponent(term.trim())}`);
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, items.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && items[activeIdx]) {
        const it = items[activeIdx];
        setOpen(false);
        router.push(`/cards/${it.id}`);
      } else {
        submit(q);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
    }
  };

  const widthCls = compact ? "max-w-md" : "max-w-2xl";

  return (
    <div ref={containerRef} className={`relative w-full ${widthCls}`}>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary">
          ⌕
        </span>
        <input
          ref={inputRef}
          type="text"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
            setActiveIdx(-1);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          placeholder="Search Pokémon, sets, cards…"
          className="w-full rounded-btn bg-bg-surface border border-border pl-9 pr-4 py-2 text-sm placeholder:text-text-tertiary focus:outline-none focus:border-accent-yellow/50 transition-colors"
        />
      </div>

      {open && q.trim().length >= 2 && (
        <div className="absolute z-50 mt-2 w-full rounded-card bg-bg-elevated border border-border shadow-xl overflow-hidden">
          {loading && items.length === 0 && (
            <div className="px-4 py-3 text-sm text-text-tertiary">Searching…</div>
          )}
          {!loading && items.length === 0 && (
            <div className="px-4 py-3 text-sm text-text-tertiary">
              No matches for &ldquo;{q}&rdquo;
            </div>
          )}
          {items.map((it, idx) => (
            <Link
              key={it.id}
              href={`/cards/${it.id}`}
              onClick={() => setOpen(false)}
              className={`flex items-center gap-3 px-3 py-2 hover:bg-bg-surface transition-colors ${
                idx === activeIdx ? "bg-bg-surface" : ""
              }`}
            >
              <div className="w-8 h-11 flex-shrink-0 relative">
                {it.image_small ? (
                  <Image
                    src={it.image_small}
                    alt=""
                    fill
                    sizes="32px"
                    className="object-contain rounded-sm"
                    unoptimized
                  />
                ) : null}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{it.name}</div>
                <div className="text-xs text-text-tertiary truncate">
                  #{it.number ?? "—"} · {it.set_name ?? it.set_id}
                  {it.rarity ? ` · ${it.rarity}` : ""}
                </div>
              </div>
              {it.market_price_usd != null && (
                <div className="text-xs font-mono text-accent-green flex-shrink-0">
                  ${it.market_price_usd.toFixed(2)}
                </div>
              )}
            </Link>
          ))}
          {items.length > 0 && (
            <button
              onClick={() => submit(q)}
              className="w-full text-left px-4 py-2 text-xs font-mono uppercase tracking-wider text-text-tertiary border-t border-border hover:text-text-primary hover:bg-bg-surface transition-colors"
            >
              See all results for &ldquo;{q}&rdquo; →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
