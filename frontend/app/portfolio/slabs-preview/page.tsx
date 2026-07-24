"use client";

/**
 * Slabs preview — two modes:
 *
 *   1. Samples — hardcoded 4 slabs across PSA / BGS / CGC / TAG, used
 *      to tune FRAME_META coordinates via the slider panel below.
 *   2. Try your card — search any card by name, pick a grader + tier,
 *      see it live-slabbed in both frame styles. Anyone (no login)
 *      can play with this to get a feel for what a graded slab of
 *      their card would look like.
 *
 * Access: /portfolio/slabs-preview (public URL, no auth).
 *
 * Coordinate tuning state persists to localStorage per style so a
 * refresh keeps your latest tuning across both modes.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import {
  FRAME_META,
  SlabFrame,
  type CardRect,
  type EmblemRect,
  type FlipRect,
} from "@/components/portfolio/SlabFrame";
import { searchCards, type Card } from "@/lib/api";

type Style = "bgs" | "psa" | "clean";
type Mode = "samples" | "try";
type Service = "PSA" | "BGS" | "CGC" | "TAG";

const SAMPLES: Array<{
  yearSet: string;
  cardName: string;
  cardImage: string;
  service: Service;
  grade: string;
  suffix?: string;
  subgrades?: [number, number, number, number];
}> = [
  {
    yearSet: "2024 Mega Evolution · #125",
    cardName: "Mega Charizard ex",
    cardImage: "https://images.pokemontcg.io/sv3/151_hires.png",
    service: "PSA",
    grade: "10",
    suffix: "Gem Mint",
  },
  {
    yearSet: "2021 Evolving Skies · #215",
    cardName: "Umbreon VMAX Alt",
    cardImage: "https://images.pokemontcg.io/swsh7/215_hires.png",
    service: "BGS",
    grade: "9.5",
    suffix: "Gem Mint",
    subgrades: [10, 9.5, 9.5, 10],
  },
  {
    yearSet: "2000 Neo Genesis · #9",
    cardName: "Lugia Holo 1st Ed",
    cardImage: "https://images.pokemontcg.io/neo1/9_hires.png",
    service: "CGC",
    grade: "10",
    suffix: "Pristine",
  },
  {
    yearSet: "2022 Lost Origin · TG30",
    cardName: "Giratina VSTAR",
    cardImage: "https://images.pokemontcg.io/swsh11/186_hires.png",
    service: "TAG",
    grade: "10",
    suffix: "Pristine",
  },
];

const GRADE_OPTIONS: Array<{ value: string; suffix?: string }> = [
  { value: "10", suffix: "Gem Mint" },
  { value: "9.5", suffix: "Mint+" },
  { value: "9", suffix: "Mint" },
  { value: "8.5", suffix: "NM-Mint" },
  { value: "8", suffix: "NM" },
  { value: "7", suffix: "NM" },
];

const LS_KEY = "slab-tune-v1";

type StyleTune = { flip: FlipRect; card: CardRect; emblem: EmblemRect };

function loadOverrides(): Record<Style, StyleTune> {
  const defaults: Record<Style, StyleTune> = {
    bgs: {
      flip: FRAME_META.bgs.flip,
      card: FRAME_META.bgs.card,
      emblem: FRAME_META.bgs.emblem,
    },
    psa: {
      flip: FRAME_META.psa.flip,
      card: FRAME_META.psa.card,
      emblem: FRAME_META.psa.emblem,
    },
    clean: {
      flip: FRAME_META.clean.flip,
      card: FRAME_META.clean.card,
      emblem: FRAME_META.clean.emblem,
    },
  };
  if (typeof window === "undefined") return defaults;
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) throw new Error("empty");
    const parsed = JSON.parse(raw);
    // Guard against older localStorage entries that pre-date any of the
    // stored shapes (added `clean` style, added `emblem` field) — fall
    // back to defaults for missing keys so the page doesn't crash
    // before the user hits Reset.
    const merge = (s: Style): StyleTune => ({
      flip: parsed[s]?.flip ?? defaults[s].flip,
      card: parsed[s]?.card ?? defaults[s].card,
      emblem: parsed[s]?.emblem ?? defaults[s].emblem,
    });
    return { bgs: merge("bgs"), psa: merge("psa"), clean: merge("clean") };
  } catch {
    return defaults;
  }
}

const parsePct = (v: string): number => parseFloat(v.replace("%", "")) || 0;
const asPct = (n: number): string => `${n}%`;

export default function SlabsPreviewPage() {
  const [mode, setMode] = useState<Mode>("samples");
  const [style, setStyle] = useState<Style>("psa");
  const [debug, setDebug] = useState(true);
  const [tune, setTune] = useState(() => loadOverrides());
  const [copied, setCopied] = useState(false);
  // Card image inset — shrinks the card inside its well without moving
  // the well itself. Global across styles (real cards are the same size
  // regardless of slab). Persisted separately from FRAME_META.
  const [cardInsetPct, setCardInsetPct] = useState<number>(() => {
    if (typeof window === "undefined") return 0;
    const raw = window.localStorage.getItem("slab-tune-v1-cardInset");
    return raw ? parseFloat(raw) || 0 : 0;
  });

  useEffect(() => {
    window.localStorage.setItem(LS_KEY, JSON.stringify(tune));
  }, [tune]);

  useEffect(() => {
    window.localStorage.setItem("slab-tune-v1-cardInset", String(cardInsetPct));
  }, [cardInsetPct]);

  const current = tune[style];

  const updateFlip = useCallback(
    (key: keyof FlipRect, value: number) => {
      setTune((prev) => ({
        ...prev,
        [style]: {
          ...prev[style],
          flip: { ...prev[style].flip, [key]: asPct(value) },
        },
      }));
    },
    [style],
  );
  const updateCard = useCallback(
    (key: keyof CardRect, value: number) => {
      setTune((prev) => ({
        ...prev,
        [style]: {
          ...prev[style],
          card: { ...prev[style].card, [key]: asPct(value) },
        },
      }));
    },
    [style],
  );
  const updateEmblem = useCallback(
    (key: keyof EmblemRect, value: number) => {
      setTune((prev) => ({
        ...prev,
        [style]: {
          ...prev[style],
          emblem: { ...prev[style].emblem, [key]: asPct(value) },
        },
      }));
    },
    [style],
  );

  const resetCurrent = () => {
    setTune((prev) => ({
      ...prev,
      [style]: {
        flip: FRAME_META[style].flip,
        card: FRAME_META[style].card,
        emblem: FRAME_META[style].emblem,
      },
    }));
  };

  const copyCode = async () => {
    const aspectRatio =
      style === "bgs" ? "797 / 1344" : style === "psa" ? "816 / 1285" : "5 / 8";
    const flipTone =
      style === "bgs" ? "on-gold" : style === "psa" ? "on-white" : "on-black";
    const snippet = `${style}: {
  src: "/slab-frame-${style}.png",
  aspectRatio: "${aspectRatio}",
  flip: { top: "${current.flip.top}", left: "${current.flip.left}", right: "${current.flip.right}", height: "${current.flip.height}" },
  card: { top: "${current.card.top}", left: "${current.card.left}", right: "${current.card.right}", bottom: "${current.card.bottom}" },
  emblem: { bottom: "${current.emblem.bottom}", left: "${current.emblem.left}", width: "${current.emblem.width}" },
  flipTone: "${flipTone}",
},`;
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      alert(snippet);
    }
  };

  return (
    <main className="min-h-screen bg-bg py-8 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-tertiary mb-2">
            Internal · Slab prototype
          </p>
          <h1 className="text-2xl sm:text-3xl font-bold text-text-primary mb-2">
            Slabs Preview
          </h1>
          <p className="text-sm text-text-secondary max-w-2xl">
            Two modes below. Sample the four grader tones to tune
            coordinates, or search any card and see what it looks like
            slabbed. Coordinate tuning persists per browser.
          </p>
        </div>

        {/* Mode tabs */}
        <div className="flex items-center gap-1 mb-4 p-1 rounded-full bg-bg-surface border border-border w-fit">
          {(["samples", "try"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={
                "px-4 py-1.5 text-xs font-mono uppercase tracking-wider rounded-full transition-colors " +
                (mode === m
                  ? "bg-accent-yellow text-gray-900 font-bold"
                  : "text-text-secondary hover:text-text-primary")
              }
            >
              {m === "samples" ? "Samples" : "Try your card"}
            </button>
          ))}
        </div>

        {/* Style + debug controls (shared) */}
        <div className="flex flex-wrap items-center gap-3 mb-6 p-3 rounded-card bg-bg-surface border border-border">
          <div className="flex items-center gap-1 p-1 rounded-full bg-bg border border-border">
            {(["bgs", "psa", "clean"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStyle(s)}
                className={
                  "px-3 py-1.5 text-xs font-mono uppercase tracking-wider rounded-full transition-colors " +
                  (style === s
                    ? "bg-accent-yellow text-gray-900 font-bold"
                    : "text-text-secondary hover:text-text-primary")
                }
              >
                Frame {s === "bgs" ? "1 · BGS" : s === "psa" ? "2 · PSA" : "3 · Clean"}
              </button>
            ))}
          </div>
          <label className="inline-flex items-center gap-2 cursor-pointer text-xs font-mono uppercase tracking-wider text-text-secondary">
            <input
              type="checkbox"
              checked={debug}
              onChange={(e) => setDebug(e.target.checked)}
              className="h-4 w-4 accent-accent-yellow"
            />
            Debug outlines
          </label>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={resetCurrent}
              className="rounded-btn border border-border px-3 py-1.5 text-xs font-mono uppercase tracking-wider text-text-secondary hover:text-text-primary hover:border-accent-yellow/40 transition-colors"
            >
              Reset
            </button>
            <button
              onClick={copyCode}
              className="rounded-btn border border-accent-yellow/40 bg-accent-yellow/10 px-3 py-1.5 text-xs font-mono uppercase tracking-wider font-bold text-accent-yellow hover:bg-accent-yellow/20 transition-colors"
            >
              {copied ? "Copied!" : "Copy code"}
            </button>
          </div>
        </div>

        {mode === "samples" ? (
          <SamplesGrid style={style} debug={debug} tune={current} cardInsetPct={cardInsetPct} />
        ) : (
          <TryYourCard style={style} debug={debug} tune={current} cardInsetPct={cardInsetPct} />
        )}

        {/* Live tuning panel — visible under both modes */}
        <div className="rounded-card bg-bg-surface border border-border p-5 sm:p-6 mt-10">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-tertiary mb-1">
                Tuning · {style === "bgs" ? "Frame 1 · BGS" : style === "psa" ? "Frame 2 · PSA" : "Frame 3 · Clean"}
              </p>
              <h2 className="text-lg font-bold text-text-primary">
                Move the flip well & card well
              </h2>
            </div>
            <span className="text-[11px] text-text-tertiary font-mono">
              Values in %, all sliders 0–100
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <fieldset className="border border-pink-500/30 rounded-btn p-4">
              <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-pink-400">
                Flip well (pink outline)
              </legend>
              <SliderRow label="top" value={parsePct(current.flip.top)} max={40} onChange={(v) => updateFlip("top", v)} />
              <SliderRow label="left" value={parsePct(current.flip.left)} max={60} onChange={(v) => updateFlip("left", v)} />
              <SliderRow label="right" value={parsePct(current.flip.right)} max={60} onChange={(v) => updateFlip("right", v)} />
              <SliderRow label="height" value={parsePct(current.flip.height)} max={30} onChange={(v) => updateFlip("height", v)} />
            </fieldset>

            <fieldset className="border border-cyan-500/30 rounded-btn p-4">
              <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-cyan-400">
                Card well (cyan outline)
              </legend>
              <SliderRow label="top" value={parsePct(current.card.top)} max={40} onChange={(v) => updateCard("top", v)} />
              <SliderRow label="left" value={parsePct(current.card.left)} max={40} onChange={(v) => updateCard("left", v)} />
              <SliderRow label="right" value={parsePct(current.card.right)} max={40} onChange={(v) => updateCard("right", v)} />
              <SliderRow label="bottom" value={parsePct(current.card.bottom)} max={30} onChange={(v) => updateCard("bottom", v)} />
            </fieldset>
          </div>

          <fieldset className="mt-6 border border-lime-500/30 rounded-btn p-4">
            <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-lime-400">
              Emblem (chartreuse outline) · per-style
            </legend>
            <p className="text-[11px] text-text-tertiary mb-2 font-mono">
              Move + resize the PullList mascot mark. bottom/left anchor
              the corner; width sets both dimensions (square).
            </p>
            <SliderRow label="bottom" value={parsePct(current.emblem.bottom)} max={90} onChange={(v) => updateEmblem("bottom", v)} />
            <SliderRow label="left" value={parsePct(current.emblem.left)} max={90} onChange={(v) => updateEmblem("left", v)} />
            <SliderRow label="width" value={parsePct(current.emblem.width)} max={60} onChange={(v) => updateEmblem("width", v)} />
          </fieldset>

          {/* Card inset — global across styles. Real cards are the
              same size regardless of slab, so this control isn't a
              per-frame FRAME_META override; it's just how much
              breathing room the card image gets INSIDE the well. */}
          <fieldset className="mt-6 border border-accent-yellow/30 rounded-btn p-4">
            <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-accent-yellow">
              Card image inset (global)
            </legend>
            <p className="text-[11px] text-text-tertiary mb-2 font-mono">
              Shrinks the card image inward without moving the well.
              0 = card fills the well edge-to-edge; 5 = 5% padding on
              all four sides. Useful when the well rect is slightly
              generous so real cards don&apos;t spill onto plastic.
            </p>
            <SliderRow
              label="inset"
              value={cardInsetPct}
              max={15}
              onChange={(v) => setCardInsetPct(v)}
            />
          </fieldset>
        </div>
      </div>
    </main>
  );
}

// ────────────────────────── Samples grid ──────────────────────────

function SamplesGrid({
  style,
  debug,
  tune,
  cardInsetPct,
}: {
  style: Style;
  debug: boolean;
  tune: StyleTune;
  cardInsetPct: number;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
      {SAMPLES.map((s) => (
        <div key={s.cardName + s.service}>
          <SlabFrame
            style={style}
            {...s}
            debug={debug}
            flipOverride={tune.flip}
            cardOverride={tune.card}
            emblemOverride={tune.emblem}
            cardInsetPct={cardInsetPct}
          />
          <p className="mt-3 text-center text-[11px] font-mono uppercase tracking-[0.12em] text-text-tertiary">
            {s.service} {s.grade}
            {s.suffix ? ` · ${s.suffix}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}

// ────────────────────────── Try-your-card ──────────────────────────

function TryYourCard({
  style,
  debug,
  tune,
  cardInsetPct,
}: {
  style: Style;
  debug: boolean;
  tune: StyleTune;
  cardInsetPct: number;
}) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [results, setResults] = useState<Card[]>([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState<Card | null>(null);
  const [service, setService] = useState<Service>("PSA");
  const [gradeIdx, setGradeIdx] = useState(0); // index into GRADE_OPTIONS

  // Debounce the search input.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    if (debouncedQuery.length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    searchCards(debouncedQuery, 1, 12, "relevance")
      .then((r) => {
        if (!cancelled) setResults(r.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  const yearSet = useMemo(() => {
    if (!picked) return "";
    const setName = (picked.set_name || picked.set_id).toUpperCase();
    return picked.number ? `${setName} · #${picked.number}` : setName;
  }, [picked]);

  const grade = GRADE_OPTIONS[gradeIdx];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {/* Left: search + picker */}
      <div>
        <label className="block text-[11px] font-mono uppercase tracking-[0.14em] text-text-tertiary mb-2">
          Search any card by name
        </label>
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. charizard, umbreon vmax, lugia neo"
            className="w-full rounded-btn bg-bg-surface border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-accent-yellow/60 transition-colors"
          />
          {loading && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-text-tertiary" />
          )}
        </div>

        {debouncedQuery.length >= 2 && (
          <div className="mt-3 grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-[420px] overflow-y-auto rounded-btn bg-bg-surface border border-border p-2">
            {results.length === 0 && !loading ? (
              <p className="col-span-full text-xs text-text-tertiary py-4 text-center font-mono">
                No matches
              </p>
            ) : (
              results.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setPicked(c)}
                  className={
                    "relative aspect-[63/88] rounded-btn overflow-hidden border transition-all " +
                    (picked?.id === c.id
                      ? "border-accent-yellow ring-2 ring-accent-yellow/40"
                      : "border-border hover:border-accent-yellow/40")
                  }
                  title={`${c.name} · ${c.set_name ?? c.set_id}`}
                >
                  {c.image_small ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={c.image_small}
                      alt={c.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full bg-bg-elevated" />
                  )}
                </button>
              ))
            )}
          </div>
        )}

        {picked && (
          <>
            <div className="mt-5">
              <label className="block text-[11px] font-mono uppercase tracking-[0.14em] text-text-tertiary mb-2">
                Grading service
              </label>
              <div className="grid grid-cols-4 gap-1.5">
                {(["PSA", "BGS", "CGC", "TAG"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setService(s)}
                    className={
                      "rounded-btn py-2 text-xs font-mono uppercase tracking-wider border transition-colors " +
                      (service === s
                        ? "bg-accent-yellow/15 border-accent-yellow/60 text-accent-yellow font-bold"
                        : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40")
                    }
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-[11px] font-mono uppercase tracking-[0.14em] text-text-tertiary mb-2">
                Grade tier
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
                {GRADE_OPTIONS.map((g, i) => (
                  <button
                    key={g.value}
                    onClick={() => setGradeIdx(i)}
                    className={
                      "rounded-btn py-2 text-xs font-mono border transition-colors " +
                      (gradeIdx === i
                        ? "bg-accent-yellow/15 border-accent-yellow/60 text-accent-yellow font-bold"
                        : "bg-bg border-border text-text-secondary hover:text-text-primary hover:border-accent-yellow/40")
                    }
                  >
                    {g.value}
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Right: live slab preview */}
      <div className="flex flex-col items-center">
        {picked ? (
          <>
            <div className="w-full max-w-[320px]">
              <SlabFrame
                style={style}
                cardName={picked.name}
                cardImage={picked.image_large ?? picked.image_small ?? undefined}
                yearSet={yearSet}
                service={service}
                grade={grade.value}
                suffix={grade.suffix}
                debug={debug}
                flipOverride={tune.flip}
                cardOverride={tune.card}
                emblemOverride={tune.emblem}
                cardInsetPct={cardInsetPct}
              />
            </div>
            <p className="mt-3 text-center text-[11px] font-mono uppercase tracking-[0.12em] text-text-tertiary">
              {service} {grade.value}
              {grade.suffix ? ` · ${grade.suffix}` : ""}
            </p>
          </>
        ) : (
          <div className="w-full max-w-[320px] aspect-[5/8] rounded-card border-2 border-dashed border-border flex items-center justify-center p-6">
            <p className="text-xs text-text-tertiary text-center font-mono uppercase tracking-wider leading-relaxed">
              Search + pick a card
              <br />
              on the left to preview
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ────────────────────────── Slider helper ──────────────────────────

function SliderRow({
  label,
  value,
  max,
  onChange,
}: {
  label: string;
  value: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3 py-1.5">
      <label className="w-14 text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
        {label}
      </label>
      <input
        type="range"
        min={0}
        max={max}
        step={0.5}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1 accent-accent-yellow"
      />
      <input
        type="number"
        min={0}
        max={max}
        step={0.5}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        className="w-14 rounded-btn bg-bg border border-border px-2 py-1 text-[11px] font-mono text-right"
      />
      <span className="text-[10px] font-mono text-text-tertiary w-3">%</span>
    </div>
  );
}
