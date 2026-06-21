"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

/**
 * Centred mascot + rotating Korean/English status line. Replaces blank
 * skeletons on full-page loads (main, /sets, /trending, /cards, /portfolio)
 * so the wait reads as personality rather than dead air.
 *
 * Two animated APNG variants:
 *   - idle: sitting + blinking + holding card (used when waiting for data
 *           on the current page — trending fetch, browse pagination, etc.)
 *   - fly:  flying diagonally + wings flapping (used by the global route-
 *           transition loader so the mascot "goes somewhere" while the next
 *           page streams in)
 *
 * The APNGs carry their own per-frame motion, so we deliberately skip the
 * old CSS bounce keyframe — stacking the two looks twitchy.
 */

type Phrase = { en: string; kr: string };

const PHRASES: Phrase[] = [
  { en: "Counting your pulls...", kr: "카드 모으는 중..." },
  { en: "Calling the trainer...", kr: "트레이너 부르는 중..." },
  { en: "Checking the prices...", kr: "가격 확인하는 중..." },
];

const ROTATION_MS = 2400;

type Size = "sm" | "md" | "lg";
type Variant = "idle" | "fly";

const SIZE_CFG: Record<Size, { px: number; text: string }> = {
  sm: { px: 56, text: "text-xs" },
  md: { px: 96, text: "text-sm" },
  lg: { px: 144, text: "text-base" },
};

const VARIANT_SRC: Record<Variant, string> = {
  idle: "/pullist-mascot.png",
  fly: "/pullist-mascot-fly.png",
};

export function MascotLoader({
  size = "md",
  variant = "idle",
  className = "",
}: {
  size?: Size;
  variant?: Variant;
  className?: string;
}) {
  const [idx, setIdx] = useState(0);
  const [lang, setLang] = useState<"kr" | "en">("kr");

  useEffect(() => {
    // Pick the user's preferred language once on mount. Browser locale-pref
    // is good enough — we don't need a global store for a loading string.
    if (typeof navigator !== "undefined") {
      const top = (navigator.language || "").toLowerCase();
      setLang(top.startsWith("ko") ? "kr" : "en");
    }
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setIdx((p) => (p + 1) % PHRASES.length);
    }, ROTATION_MS);
    return () => clearInterval(id);
  }, []);

  const cfg = SIZE_CFG[size];
  const phrase = PHRASES[idx];

  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 py-8 ${className}`}
      role="status"
      aria-live="polite"
    >
      <div
        className="relative"
        style={{ width: cfg.px, height: cfg.px }}
      >
        <Image
          src={VARIANT_SRC[variant]}
          alt=""
          fill
          sizes={`${cfg.px}px`}
          className="object-contain drop-shadow-lg"
          priority
          unoptimized
        />
      </div>
      <p
        key={idx}
        className={`${cfg.text} text-text-secondary font-medium animate-mascot-fade tabular-nums`}
      >
        {phrase[lang]}
      </p>
    </div>
  );
}
