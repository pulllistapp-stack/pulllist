"use client";

type Slice = {
  label: string;
  value: number;
  color: string;
};

const PALETTE = [
  "#FFCB05", // amber (brand)
  "#5BC9C2", // mint
  "#60a5fa", // blue
  "#a78bfa", // violet
  "#f472b6", // pink
  "#fb923c", // orange
  "#34d399", // emerald
  "#94a3b8", // slate
];

export function AssetMixDonut({ slices, total }: { slices: Slice[]; total: number }) {
  if (total <= 0 || slices.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-text-tertiary">
        No assets yet
      </div>
    );
  }

  const size = 160;
  const strokeWidth = 18;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  let accumulated = 0;
  const segments = slices.map((s) => {
    const fraction = s.value / total;
    const dash = fraction * circumference;
    const gap = circumference - dash;
    const offset = -accumulated;
    accumulated += dash;
    return { ...s, fraction, dash, gap, offset };
  });

  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.08}
            strokeWidth={strokeWidth}
          />
          {segments.map((seg, i) => (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${seg.dash} ${seg.gap}`}
              strokeDashoffset={seg.offset}
              strokeLinecap="butt"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-xs text-text-tertiary font-mono uppercase tracking-wider">
            Slices
          </div>
          <div className="text-2xl font-bold text-text-primary font-mono">
            {slices.length}
          </div>
        </div>
      </div>

      <ul className="flex-1 min-w-0 flex flex-col gap-1.5 text-sm">
        {segments.map((seg) => (
          <li key={seg.label} className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ background: seg.color }}
              />
              <span className="truncate text-text-secondary">{seg.label}</span>
            </div>
            <span className="font-mono text-xs font-semibold text-text-primary shrink-0">
              {(seg.fraction * 100).toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export { PALETTE };
