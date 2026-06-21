"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "./AuthProvider";
import { FilterOptions, getFilterOptions } from "@/lib/api";
import { rarityChipClass } from "@/lib/rarity";

type Props = {
  /** Path the filter form submits to. Default: current path. */
  basePath?: string;
  /** Set id pre-fixed (hides the Set filter section). */
  lockedSetId?: string;
  /** Pre-fixed search query (hides the q filter section). */
  lockedQ?: string;
};

const RARITY_GROUPS: Record<string, string[]> = {
  Common: ["Common"],
  Uncommon: ["Uncommon"],
  Rare: ["Rare"],
  "Rare Holo": ["Rare Holo", "Rare Holo 1st Edition"],
  "Double / Triple / Ultra": [
    "Double Rare",
    "Triple Rare",
    "Ultra Rare",
    "Rare Ultra",
  ],
  "Holo EX/GX/V/VMAX/VSTAR": [
    "Rare Holo EX",
    "Rare Holo GX",
    "Rare Holo V",
    "Rare Holo VMAX",
    "Rare Holo VSTAR",
    "Rare Holo ex",
  ],
  "Illustration": [
    "Illustration Rare",
    "Special Illustration Rare",
  ],
  Secret: [
    "Rare Secret",
    "Rare Rainbow",
    "Hyper Rare",
    "Rare Shiny",
    "Rare Shiny GX",
    "Shiny Rare",
    "Shiny Rare V",
    "Shiny Rare VMAX",
    "Shiny Ultra Rare",
    "Radiant Rare",
    "Amazing Rare",
  ],
  Mega: ["Mega Hyper Rare", "MEGA_ATTACK_RARE"],
  Promo: ["Promo", "Classic Collection"],
  Other: [
    "ACE SPEC Rare",
    "LEGEND",
    "Rare ACE",
    "Rare BREAK",
    "Rare Holo LV.X",
    "Rare Prime",
    "Rare Prism Star",
    "Rare Shining",
    "Rare Holo ☆",
  ],
};

// Rarity color tier system lives in @/lib/rarity — shared with TrendingPage,
// CardThumb, etc. so chips look consistent everywhere.

function readCsv(params: URLSearchParams, key: string): Set<string> {
  const raw = params.get(key);
  if (!raw) return new Set();
  return new Set(raw.split(",").filter(Boolean));
}

export function FilterSidebar({ basePath, lockedSetId, lockedQ }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const { user } = useAuth();

  const [options, setOptions] = useState<FilterOptions | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Set page → scope options to *that set's* card distribution so the
        // sidebar doesn't list rarities/types/artists that don't exist here.
        const opts = await getFilterOptions(lockedSetId);
        if (!cancelled) setOptions(opts);
      } catch {
        // non-fatal
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lockedSetId]);

  const selSets = readCsv(params, "set_id");
  const selRarity = readCsv(params, "rarity");
  const selSupertype = readCsv(params, "supertype");
  const selType = readCsv(params, "type");
  const selSubtype = readCsv(params, "subtype");
  const selCondition = readCsv(params, "condition");
  const selArtist = readCsv(params, "artist");
  const hpMin = params.get("hp_min") ?? "";
  const hpMax = params.get("hp_max") ?? "";
  const priceMin = params.get("price_min") ?? "";
  const priceMax = params.get("price_max") ?? "";
  const owned = params.get("owned") ?? "";
  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "relevance";

  const activeCount = useMemo(() => {
    let n = 0;
    if (!lockedSetId && selSets.size) n += selSets.size;
    n += selRarity.size + selSupertype.size + selType.size + selSubtype.size;
    n += selArtist.size;
    if (selCondition.size) n += selCondition.size;
    if (hpMin) n++;
    if (hpMax) n++;
    if (priceMin) n++;
    if (priceMax) n++;
    if (owned) n++;
    return n;
  }, [
    lockedSetId,
    selSets,
    selRarity,
    selSupertype,
    selType,
    selSubtype,
    selCondition,
    selArtist,
    hpMin,
    hpMax,
    priceMin,
    priceMax,
    owned,
  ]);

  const writeParam = useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v === null || v === "") next.delete(k);
        else next.set(k, v);
      }
      next.delete("page");
      const path = basePath ?? window.location.pathname;
      router.push(`${path}?${next.toString()}`);
    },
    [params, router, basePath],
  );

  const toggleInCsv = (key: string, value: string) => {
    const current = readCsv(params, key);
    if (current.has(value)) current.delete(value);
    else current.add(value);
    writeParam({ [key]: current.size ? [...current].join(",") : null });
  };

  const clearAll = () => {
    const next = new URLSearchParams();
    if (lockedQ && q) next.set("q", q);
    const path = basePath ?? window.location.pathname;
    router.push(`${path}?${next.toString()}`);
  };

  if (!options) {
    return (
      <aside className="text-sm text-text-tertiary p-4">Loading filters…</aside>
    );
  }

  // Group rarities — collapse anything not in options into "Other"
  const rarityKeys = Object.keys(RARITY_GROUPS);
  const knownRarities = new Set(
    rarityKeys.flatMap((k) => RARITY_GROUPS[k]),
  );
  const extraRarities = options.rarities.filter((r) => !knownRarities.has(r));
  const groupedRarities = rarityKeys.map((k) => ({
    label: k,
    rarities: RARITY_GROUPS[k].filter((r) => options.rarities.includes(r)),
  })).filter((g) => g.rarities.length > 0);
  if (extraRarities.length > 0) {
    groupedRarities.push({ label: "Misc", rarities: extraRarities });
  }

  return (
    <aside className="space-y-5 text-sm">
      <header className="flex items-center justify-between">
        <h2 className="font-mono uppercase tracking-wider text-text-tertiary text-xs">
          Filters {activeCount > 0 && (
            <span className="ml-1 text-accent-yellow">({activeCount})</span>
          )}
        </h2>
        {activeCount > 0 && (
          <button
            onClick={clearAll}
            className="text-xs text-text-tertiary hover:text-text-primary"
          >
            Clear all
          </button>
        )}
      </header>

      {/* Sort */}
      <Section title="Sort">
        <select
          value={sort}
          onChange={(e) => writeParam({ sort: e.target.value })}
          className="w-full rounded-btn bg-bg-surface border border-border px-2.5 py-1.5 text-sm focus:outline-none focus:border-accent-yellow/50"
        >
          <option value="relevance">Relevance (price)</option>
          <option value="price_desc">Price · high to low</option>
          <option value="price_asc">Price · low to high</option>
          <option value="newest">Newest set</option>
          <option value="name_asc">Name · A→Z</option>
          <option value="name_desc">Name · Z→A</option>
          <option value="hp_desc">HP · high to low</option>
          <option value="hp_asc">HP · low to high</option>
          <option value="number_asc">Card number</option>
        </select>
      </Section>

      {/* Collection (auth only) */}
      {user && (
        <Section title="My collection">
          <div className="flex gap-1.5 mb-2">
            {[
              { v: "", label: "All" },
              { v: "in", label: "Owned" },
              { v: "not_in", label: "Missing" },
            ].map((opt) => (
              <button
                key={opt.v}
                onClick={() => writeParam({ owned: opt.v || null })}
                className={`flex-1 rounded-chip px-2 py-1 text-xs transition-colors ${
                  owned === opt.v
                    ? "bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30"
                    : "bg-bg-surface text-text-secondary border border-border hover:border-accent-yellow/40"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1">
            {options.conditions.map((c) => (
              <Chip
                key={c}
                active={selCondition.has(c)}
                onClick={() => toggleInCsv("condition", c)}
              >
                {c}
              </Chip>
            ))}
          </div>
        </Section>
      )}

      {!lockedSetId && (
        <Section title="Set" defaultOpen={false}>
          <SearchableChecklist
            items={options.sets.map((s) => ({ value: s.id, label: s.name }))}
            selected={selSets}
            onToggle={(v) => toggleInCsv("set_id", v)}
            placeholder="Filter sets…"
          />
        </Section>
      )}

      {/* Supertype */}
      <Section title="Card type">
        <div className="flex flex-wrap gap-1">
          {options.supertypes.map((st) => (
            <Chip
              key={st}
              active={selSupertype.has(st)}
              onClick={() => toggleInCsv("supertype", st)}
            >
              {st}
            </Chip>
          ))}
        </div>
      </Section>

      {/* Energy type */}
      <Section title="Energy type">
        <div className="flex flex-wrap gap-1">
          {options.types.map((t) => (
            <Chip
              key={t}
              active={selType.has(t)}
              onClick={() => toggleInCsv("type", t)}
            >
              {t}
            </Chip>
          ))}
        </div>
      </Section>

      {/* Rarity */}
      <Section title="Rarity">
        <div className="space-y-2">
          {groupedRarities.map((g) => (
            <div key={g.label}>
              <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-1">
                {g.label}
              </div>
              <div className="flex flex-wrap gap-1">
                {g.rarities.map((r) => (
                  <RarityChip
                    key={r}
                    rarity={r}
                    active={selRarity.has(r)}
                    onClick={() => toggleInCsv("rarity", r)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Subtype (stage, ability...) */}
      <Section title="Stage / effect" defaultOpen={false}>
        <div className="flex flex-wrap gap-1 max-h-48 overflow-y-auto">
          {options.subtypes.map((st) => (
            <Chip
              key={st}
              active={selSubtype.has(st)}
              onClick={() => toggleInCsv("subtype", st)}
            >
              {st}
            </Chip>
          ))}
        </div>
      </Section>

      {/* HP range */}
      <Section title="HP range">
        <RangeInputs
          min={hpMin}
          max={hpMax}
          placeholder={[0, options.hp_max]}
          onChange={(min, max) =>
            writeParam({ hp_min: min || null, hp_max: max || null })
          }
        />
      </Section>

      {/* Price range */}
      <Section title="Price (USD)">
        <RangeInputs
          min={priceMin}
          max={priceMax}
          placeholder={[0, options.price_max]}
          onChange={(min, max) =>
            writeParam({ price_min: min || null, price_max: max || null })
          }
        />
      </Section>

      {/* Illustrator — checklist (multi-select) */}
      <Section title="Illustrator" defaultOpen={false}>
        <SearchableChecklist
          items={options.artists.map((a) => ({
            value: a.name,
            label: a.name,
            secondary: `${a.count}`,
          }))}
          selected={selArtist}
          onToggle={(v) => toggleInCsv("artist", v)}
          placeholder="Filter illustrators…"
        />
      </Section>
    </aside>
  );
}

function SearchableChecklist({
  items,
  selected,
  onToggle,
  placeholder,
}: {
  items: { value: string; label: string; secondary?: string }[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  placeholder: string;
}) {
  const [query, setQuery] = useState("");
  const lower = query.trim().toLowerCase();
  const filtered = lower
    ? items.filter((it) => it.label.toLowerCase().includes(lower))
    : items;

  return (
    <div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-btn bg-bg-surface border border-border px-2.5 py-1.5 text-xs mb-2 focus:outline-none focus:border-accent-yellow/50"
      />
      <div className="max-h-56 overflow-y-auto pr-1 space-y-1 overscroll-contain">
        {filtered.length === 0 ? (
          <div className="text-xs text-text-tertiary px-1 py-2">No matches</div>
        ) : (
          filtered.map((it) => (
            <label
              key={it.value}
              className="flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary cursor-pointer"
            >
              <input
                type="checkbox"
                checked={selected.has(it.value)}
                onChange={() => onToggle(it.value)}
                className="accent-accent-yellow"
              />
              <span className="truncate flex-1">{it.label}</span>
              {it.secondary && (
                <span className="text-text-tertiary font-mono text-[10px]">
                  {it.secondary}
                </span>
              )}
            </label>
          ))
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between mb-2 text-text-secondary hover:text-text-primary"
      >
        <span className="text-xs font-mono uppercase tracking-wider">{title}</span>
        <span className="text-text-tertiary text-xs">{open ? "−" : "+"}</span>
      </button>
      {open && <div>{children}</div>}
    </section>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-chip px-2 py-0.5 text-[11px] transition-colors ${
        active
          ? "bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30"
          : "bg-bg-surface text-text-secondary border border-border hover:border-accent-yellow/40"
      }`}
    >
      {children}
    </button>
  );
}

/**
 * Chip variant that color-codes by Pokémon TCG rarity tier — Common is muted
 * gray, hits get distinct hues, chase cards (SIR / Mega Hyper / Hyper Rare)
 * get gradient fills. Lets you scan the sidebar by color instead of reading.
 */
function RarityChip({
  rarity,
  active,
  onClick,
}: {
  rarity: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-chip px-2 py-0.5 text-[11px] font-medium transition-all ${rarityChipClass(
        rarity,
        active,
      )}`}
      title={rarity}
    >
      {rarity}
    </button>
  );
}

function RangeInputs({
  min,
  max,
  placeholder,
  onChange,
}: {
  min: string;
  max: string;
  placeholder: [number, number];
  onChange: (min: string, max: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        defaultValue={min}
        placeholder={String(placeholder[0])}
        onBlur={(e) => onChange(e.target.value, max)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onChange((e.target as HTMLInputElement).value, max);
        }}
        className="w-full rounded-btn bg-bg-surface border border-border px-2 py-1 text-sm font-mono focus:outline-none focus:border-accent-yellow/50"
      />
      <span className="text-text-tertiary text-xs">–</span>
      <input
        type="number"
        defaultValue={max}
        placeholder={String(placeholder[1])}
        onBlur={(e) => onChange(min, e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onChange(min, (e.target as HTMLInputElement).value);
        }}
        className="w-full rounded-btn bg-bg-surface border border-border px-2 py-1 text-sm font-mono focus:outline-none focus:border-accent-yellow/50"
      />
    </div>
  );
}
