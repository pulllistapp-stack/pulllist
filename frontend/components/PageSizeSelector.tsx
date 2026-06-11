"use client";

export const PAGE_SIZES = [30, 50, 100] as const;
export const DEFAULT_PAGE_SIZE = 50;

type Props = {
  value: number;
  onChange: (size: number) => void;
};

export function PageSizeSelector({ value, onChange }: Props) {
  return (
    <div
      className="inline-flex items-center rounded-btn border border-border overflow-hidden"
      role="radiogroup"
      aria-label="Cards per page"
    >
      <span className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary border-r border-border">
        per page
      </span>
      {PAGE_SIZES.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          role="radio"
          aria-checked={value === s}
          className={`px-3 py-1 text-xs font-mono transition-colors ${
            value === s
              ? "bg-accent-yellow/15 text-accent-yellow"
              : "text-text-secondary hover:text-text-primary hover:bg-bg-surface"
          }`}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
