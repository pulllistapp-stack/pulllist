"use client";

import Image from "next/image";
import Link from "next/link";
import { Box, Package } from "lucide-react";

import type { Product } from "@/lib/api";

const TYPE_LABEL: Record<Product["product_type"], string> = {
  booster_box: "Booster Box",
  etb: "Elite Trainer Box",
  booster_bundle: "Booster Bundle",
  premium_collection: "Premium Collection",
  tin: "Tin",
  blister: "Blister",
  build_battle: "Build & Battle",
  sleeved_booster: "Sleeved Booster",
  other: "Other",
};

const TYPE_ACCENT: Record<Product["product_type"], string> = {
  booster_box: "text-accent-yellow",
  etb: "text-teal-400",
  booster_bundle: "text-emerald-400",
  premium_collection: "text-purple-400",
  tin: "text-orange-400",
  blister: "text-blue-400",
  build_battle: "text-pink-400",
  sleeved_booster: "text-sky-400",
  other: "text-text-secondary",
};

function fmtPrice(v: number | null): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export function ProductCard({ product }: { product: Product }) {
  const accent = TYPE_ACCENT[product.product_type];
  return (
    <Link
      href={`/products/${product.id}`}
      className="group flex flex-col rounded-card border border-border bg-bg-surface hover:border-accent-yellow/40 transition-colors overflow-hidden"
    >
      <div className="relative aspect-[4/3] bg-bg-elevated flex items-center justify-center">
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.name}
            fill
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
            className="object-contain p-3 group-hover:scale-[1.03] transition-transform"
            unoptimized
          />
        ) : (
          <div className="flex flex-col items-center gap-1 text-text-tertiary">
            <Package className="h-8 w-8" />
            <span className="text-[10px] uppercase tracking-wider">
              No image
            </span>
          </div>
        )}
        <span
          className={
            "absolute top-2 left-2 inline-flex items-center gap-1 rounded-full bg-black/70 backdrop-blur-sm px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider " +
            accent
          }
        >
          <Box className="h-2.5 w-2.5" />
          {TYPE_LABEL[product.product_type]}
        </span>
      </div>
      <div className="p-3 flex-1 flex flex-col gap-1">
        <div className="text-[10px] uppercase tracking-wider text-text-tertiary font-mono truncate">
          {product.set_name ?? "—"}
        </div>
        <div className="text-sm font-semibold text-text-primary line-clamp-2 flex-1">
          {product.name}
        </div>
        <div className="flex items-baseline justify-between mt-1">
          <span className="text-base font-extrabold text-accent-green">
            {fmtPrice(product.market_price_usd)}
          </span>
          {product.packs_per_box && (
            <span className="text-[10px] font-mono text-text-tertiary">
              {product.packs_per_box} packs
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
