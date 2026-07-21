"use client";

/**
 * Slabs preview — internal-only sandbox for tuning the SlabFrame
 * component. Renders both frame styles side by side across all four
 * graders plus a BGS-with-subgrades case, over hardcoded sample cards.
 *
 * Not linked from the app nav. Access directly at /portfolio/slabs-preview.
 * Once the coordinates + typography feel right, we lift this into the
 * real /portfolio/slabs page and hook it up to CollectionItem data.
 */

import { useState } from "react";

import { SlabFrame } from "@/components/portfolio/SlabFrame";

// A handful of visually-distinct cards so we can see how the frame
// treats holo vs full-art vs vintage etc. Images pulled from the
// public pokemontcg API mirror — same source the rest of the app uses.
const SAMPLES: Array<{
  yearSet: string;
  cardName: string;
  cardImage: string;
}> = [
  {
    yearSet: "2024 Mega Evolution · #125",
    cardName: "Mega Charizard ex",
    cardImage:
      "https://images.pokemontcg.io/sv3/151_hires.png",
  },
  {
    yearSet: "2021 Evolving Skies · #215",
    cardName: "Umbreon VMAX Alt",
    cardImage:
      "https://images.pokemontcg.io/swsh7/215_hires.png",
  },
  {
    yearSet: "2000 Neo Genesis · #9",
    cardName: "Lugia Holo 1st Ed",
    cardImage:
      "https://images.pokemontcg.io/neo1/9_hires.png",
  },
  {
    yearSet: "2022 Lost Origin · TG30",
    cardName: "Giratina VSTAR",
    cardImage:
      "https://images.pokemontcg.io/swsh11/186_hires.png",
  },
];

export default function SlabsPreviewPage() {
  const [style, setStyle] = useState<"bgs" | "psa">("bgs");
  const [debug, setDebug] = useState(false);

  return (
    <main className="min-h-screen bg-bg py-10 px-4 sm:px-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-8">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-tertiary mb-2">
            Internal · Prototype
          </p>
          <h1 className="text-2xl sm:text-3xl font-bold text-text-primary mb-2">
            Slabs Preview
          </h1>
          <p className="text-sm text-text-secondary max-w-2xl">
            Sandbox for tuning the SlabFrame component before it lands
            on the real /portfolio/slabs page. Toggle between frame
            styles + debug outlines below. If a well doesn&apos;t line
            up, edit the FRAME_META coords in{" "}
            <code className="font-mono text-xs text-accent-yellow">
              components/portfolio/SlabFrame.tsx
            </code>
            .
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mb-8 p-3 rounded-card bg-bg-surface border border-border">
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
          <span className="text-[11px] text-text-tertiary ml-auto">
            Pink = flip well · Cyan = card well
          </span>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8">
          <div>
            <SlabFrame
              style={style}
              yearSet={SAMPLES[0].yearSet}
              cardName={SAMPLES[0].cardName}
              cardImage={SAMPLES[0].cardImage}
              service="PSA"
              grade="10"
              suffix="Gem Mint"
              debug={debug}
            />
            <Caption text="PSA 10 · Gem Mint" />
          </div>

          <div>
            <SlabFrame
              style={style}
              yearSet={SAMPLES[1].yearSet}
              cardName={SAMPLES[1].cardName}
              cardImage={SAMPLES[1].cardImage}
              service="BGS"
              grade="9.5"
              suffix="Gem Mint"
              subgrades={[10, 9.5, 9.5, 10]}
              debug={debug}
            />
            <Caption text="BGS 9.5 · with subgrades" />
          </div>

          <div>
            <SlabFrame
              style={style}
              yearSet={SAMPLES[2].yearSet}
              cardName={SAMPLES[2].cardName}
              cardImage={SAMPLES[2].cardImage}
              service="CGC"
              grade="10"
              suffix="Pristine"
              debug={debug}
            />
            <Caption text="CGC 10 · Pristine" />
          </div>

          <div>
            <SlabFrame
              style={style}
              yearSet={SAMPLES[3].yearSet}
              cardName={SAMPLES[3].cardName}
              cardImage={SAMPLES[3].cardImage}
              service="TAG"
              grade="10"
              suffix="Pristine"
              debug={debug}
            />
            <Caption text="TAG 10 · Pristine" />
          </div>
        </div>

        {/* Tuning cheatsheet */}
        <div className="mt-16 p-5 rounded-card bg-bg-surface border border-border max-w-3xl">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-tertiary mb-3">
            Tuning cheatsheet
          </p>
          <ul className="text-xs text-text-secondary space-y-2 leading-relaxed">
            <li>
              <strong className="text-text-primary">Flip well off?</strong>{" "}
              Edit <code className="font-mono text-accent-yellow">FRAME_META[style].flip</code>{" "}
              — top / left / right / height as % of frame image.
            </li>
            <li>
              <strong className="text-text-primary">Card window off?</strong>{" "}
              Edit <code className="font-mono text-accent-yellow">FRAME_META[style].card</code>{" "}
              — top / left / right / bottom as %.
            </li>
            <li>
              <strong className="text-text-primary">Grader accent color?</strong>{" "}
              Edit <code className="font-mono text-accent-yellow">SERVICE_ACCENT</code>{" "}
              at the top of SlabFrame.tsx.
            </li>
            <li>
              <strong className="text-text-primary">10-halo intensity?</strong>{" "}
              <code className="font-mono text-accent-yellow">opacity: 0.18</code> on the
              perfect-10 halo div — bump for more glow, drop for less.
            </li>
          </ul>
        </div>
      </div>
    </main>
  );
}

function Caption({ text }: { text: string }) {
  return (
    <p className="mt-3 text-center text-[11px] font-mono uppercase tracking-[0.12em] text-text-tertiary">
      {text}
    </p>
  );
}
