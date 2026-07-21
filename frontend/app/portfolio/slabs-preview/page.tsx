"use client";

/**
 * Slabs preview — live-tuning sandbox for the SlabFrame component.
 *
 * Access: /portfolio/slabs-preview (public URL, no auth). Share the
 * link with anyone; nothing on this page reads user data.
 *
 * The tuning panel writes into localStorage per frame style so a
 * refresh keeps your latest coord values. Hit "Reset" to restore the
 * FRAME_META defaults, "Copy code" to grab the current values as a
 * TypeScript snippet you can paste into SlabFrame.tsx.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  FRAME_META,
  SlabFrame,
  type CardRect,
  type FlipRect,
} from "@/components/portfolio/SlabFrame";

type Style = "bgs" | "psa";

const SAMPLES: Array<{
  yearSet: string;
  cardName: string;
  cardImage: string;
  service: "PSA" | "BGS" | "CGC" | "TAG";
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

const LS_KEY = "slab-tune-v1";

function loadOverrides(): {
  bgs: { flip: FlipRect; card: CardRect };
  psa: { flip: FlipRect; card: CardRect };
} {
  if (typeof window === "undefined") {
    return {
      bgs: { flip: FRAME_META.bgs.flip, card: FRAME_META.bgs.card },
      psa: { flip: FRAME_META.psa.flip, card: FRAME_META.psa.card },
    };
  }
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) throw new Error("empty");
    return JSON.parse(raw);
  } catch {
    return {
      bgs: { flip: FRAME_META.bgs.flip, card: FRAME_META.bgs.card },
      psa: { flip: FRAME_META.psa.flip, card: FRAME_META.psa.card },
    };
  }
}

// Convert "12.5%" → 12.5 for sliders and back.
const parsePct = (v: string): number => parseFloat(v.replace("%", "")) || 0;
const asPct = (n: number): string => `${n}%`;

export default function SlabsPreviewPage() {
  const [style, setStyle] = useState<Style>("psa");
  const [debug, setDebug] = useState(true);
  const [tune, setTune] = useState(() => loadOverrides());
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(LS_KEY, JSON.stringify(tune));
  }, [tune]);

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

  const resetCurrent = () => {
    setTune((prev) => ({
      ...prev,
      [style]: { flip: FRAME_META[style].flip, card: FRAME_META[style].card },
    }));
  };

  const copyCode = async () => {
    const snippet = `${style}: {
  src: "/slab-frame-${style}.png",
  aspectRatio: "${style === "bgs" ? "797 / 1344" : "816 / 1285"}",
  flip: { top: "${current.flip.top}", left: "${current.flip.left}", right: "${current.flip.right}", height: "${current.flip.height}" },
  card: { top: "${current.card.top}", left: "${current.card.left}", right: "${current.card.right}", bottom: "${current.card.bottom}" },
  flipTone: "${style === "bgs" ? "on-gold" : "on-white"}",
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
            Internal · Live tuning
          </p>
          <h1 className="text-2xl sm:text-3xl font-bold text-text-primary mb-2">
            Slabs Preview
          </h1>
          <p className="text-sm text-text-secondary max-w-2xl">
            Adjust flip well + card well coordinates live below. Values
            persist in your browser. Hit <strong>Copy code</strong> and
            paste into <code className="font-mono text-xs text-accent-yellow">FRAME_META</code>{" "}
            when you like them.
          </p>
        </div>

        {/* Style + debug controls */}
        <div className="flex flex-wrap items-center gap-3 mb-6 p-3 rounded-card bg-bg-surface border border-border">
          <div className="flex items-center gap-1 p-1 rounded-full bg-bg border border-border">
            {(["bgs", "psa"] as const).map((s) => (
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
                Frame {s === "bgs" ? "1 · BGS" : "2 · PSA"}
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

        {/* Slab grid — 1 mobile / 2 tablet / 4 desktop */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8 mb-10">
          {SAMPLES.map((s) => (
            <div key={s.cardName + s.service}>
              <SlabFrame
                style={style}
                {...s}
                debug={debug}
                flipOverride={current.flip}
                cardOverride={current.card}
              />
              <p className="mt-3 text-center text-[11px] font-mono uppercase tracking-[0.12em] text-text-tertiary">
                {s.service} {s.grade}
                {s.suffix ? ` · ${s.suffix}` : ""}
              </p>
            </div>
          ))}
        </div>

        {/* Live tuning panel */}
        <div className="rounded-card bg-bg-surface border border-border p-5 sm:p-6">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-tertiary mb-1">
                Tuning · {style === "bgs" ? "Frame 1 · BGS" : "Frame 2 · PSA"}
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
            {/* Flip well tuner */}
            <fieldset className="border border-pink-500/30 rounded-btn p-4">
              <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-pink-400">
                Flip well (pink outline)
              </legend>
              <SliderRow
                label="top"
                value={parsePct(current.flip.top)}
                max={40}
                onChange={(v) => updateFlip("top", v)}
              />
              <SliderRow
                label="left"
                value={parsePct(current.flip.left)}
                max={60}
                onChange={(v) => updateFlip("left", v)}
              />
              <SliderRow
                label="right"
                value={parsePct(current.flip.right)}
                max={60}
                onChange={(v) => updateFlip("right", v)}
              />
              <SliderRow
                label="height"
                value={parsePct(current.flip.height)}
                max={30}
                onChange={(v) => updateFlip("height", v)}
              />
            </fieldset>

            {/* Card well tuner */}
            <fieldset className="border border-cyan-500/30 rounded-btn p-4">
              <legend className="px-2 text-[10px] font-mono uppercase tracking-[0.14em] text-cyan-400">
                Card well (cyan outline)
              </legend>
              <SliderRow
                label="top"
                value={parsePct(current.card.top)}
                max={40}
                onChange={(v) => updateCard("top", v)}
              />
              <SliderRow
                label="left"
                value={parsePct(current.card.left)}
                max={40}
                onChange={(v) => updateCard("left", v)}
              />
              <SliderRow
                label="right"
                value={parsePct(current.card.right)}
                max={40}
                onChange={(v) => updateCard("right", v)}
              />
              <SliderRow
                label="bottom"
                value={parsePct(current.card.bottom)}
                max={30}
                onChange={(v) => updateCard("bottom", v)}
              />
            </fieldset>
          </div>

          <details className="mt-5 text-xs">
            <summary className="cursor-pointer text-text-tertiary font-mono uppercase tracking-wider hover:text-text-secondary">
              Current values (for pasting)
            </summary>
            <pre className="mt-2 p-3 rounded-btn bg-bg border border-border overflow-x-auto text-[11px] leading-relaxed">
{`${style}: {
  src: "/slab-frame-${style}.png",
  aspectRatio: "${style === "bgs" ? "797 / 1344" : "816 / 1285"}",
  flip: { top: "${current.flip.top}", left: "${current.flip.left}", right: "${current.flip.right}", height: "${current.flip.height}" },
  card: { top: "${current.card.top}", left: "${current.card.left}", right: "${current.card.right}", bottom: "${current.card.bottom}" },
  flipTone: "${style === "bgs" ? "on-gold" : "on-white"}",
},`}
            </pre>
          </details>
        </div>
      </div>
    </main>
  );
}

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
