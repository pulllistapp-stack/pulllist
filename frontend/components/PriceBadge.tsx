type Props = {
  price: number | null | undefined;
  label?: string;
  size?: "sm" | "md" | "lg";
};

export function PriceBadge({ price, label, size = "sm" }: Props) {
  if (price == null) return null;
  const sizeCls =
    size === "lg" ? "text-base px-3 py-1" : size === "md" ? "text-sm px-2.5 py-1" : "text-xs px-2 py-0.5";
  return (
    <span
      className={`inline-flex items-baseline gap-1 rounded-chip bg-accent-green/10 text-accent-green font-mono font-medium ${sizeCls}`}
      title={label ?? "Market price"}
    >
      <span className="opacity-70">$</span>
      <span>{price.toFixed(2)}</span>
    </span>
  );
}
