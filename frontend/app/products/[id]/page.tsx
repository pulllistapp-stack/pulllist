import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowUpRight, Box, TrendingDown, TrendingUp } from "lucide-react";

import { ProductLiveListings } from "@/components/products/ProductLiveListings";
import { ProductOwnButtons } from "@/components/products/ProductOwnButtons";
import { ProductPriceChart } from "@/components/products/ProductPriceChart";
import { getProduct } from "@/lib/api";

export const dynamic = "force-dynamic";

const TYPE_LABEL: Record<string, string> = {
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

function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1000) return `$${Math.round(v).toLocaleString()}`;
  return `$${v.toFixed(2)}`;
}

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let product;
  try {
    product = await getProduct(id);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  const ev = product.ev;
  const premium = ev?.premium_pct;

  return (
    <main className="mx-auto max-w-6xl px-4 sm:px-6 py-8">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/products" className="hover:text-text-primary">
          Sealed products
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary line-clamp-1">{product.name}</span>
      </nav>

      <div className="grid gap-8 md:grid-cols-2">
        {/* Image */}
        <div className="rounded-card border border-border bg-bg-surface aspect-[4/3] relative flex items-center justify-center">
          {product.image_url ? (
            <Image
              src={product.image_url}
              alt={product.name}
              fill
              className="object-contain p-6"
              unoptimized
              priority
            />
          ) : (
            <div className="text-text-tertiary text-sm">No image available</div>
          )}
        </div>

        {/* Meta + price */}
        <div>
          <div className="text-[10px] uppercase tracking-widest text-text-tertiary font-mono mb-1">
            {product.set_name ?? "—"}
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight mb-2">
            {product.name}
          </h1>
          <div className="flex items-center gap-2 mb-4">
            <span className="inline-flex items-center gap-1 rounded-full border border-border bg-bg-surface px-2 py-0.5 text-xs font-mono uppercase tracking-wider text-accent-yellow">
              <Box className="h-3 w-3" />
              {TYPE_LABEL[product.product_type] ?? product.product_type}
            </span>
            {product.packs_per_box && (
              <span className="rounded-full border border-border bg-bg-surface px-2 py-0.5 text-xs font-mono text-text-secondary">
                {product.packs_per_box} packs
              </span>
            )}
          </div>

          <div className="flex items-baseline gap-3 mb-2">
            <span className="text-4xl font-extrabold text-accent-green">
              {fmtPrice(product.market_price_usd)}
            </span>
            {product.low_price_usd != null && product.high_price_usd != null && (
              <span className="text-xs font-mono text-text-tertiary">
                {fmtPrice(product.low_price_usd)} –{" "}
                {fmtPrice(product.high_price_usd)}
              </span>
            )}
          </div>
          {product.msrp_usd && (
            <div className="text-xs text-text-tertiary mb-4">
              MSRP {fmtPrice(product.msrp_usd)}
            </div>
          )}

          {product.tcgplayer_url && (
            <a
              href={product.tcgplayer_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-accent-yellow text-bg font-semibold px-4 py-2 text-sm hover:brightness-110"
            >
              Buy on TCGplayer
              <ArrowUpRight className="h-4 w-4" />
            </a>
          )}

          <ProductOwnButtons productId={product.id} productName={product.name} />

          {ev && ev.box_ev_usd != null && (
            <div className="mt-6 rounded-card border border-border bg-bg-surface p-4">
              <div className="flex items-baseline justify-between mb-2">
                <h2 className="text-sm font-bold text-text-primary">
                  Estimated value
                </h2>
                <span className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                  Beta · rough estimate
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-text-tertiary">
                    Per pack (Est.)
                  </div>
                  <div className="font-extrabold text-text-primary">
                    {fmtPrice(ev.pack_ev_usd)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-text-tertiary">
                    Whole product (Est.)
                  </div>
                  <div className="font-extrabold text-text-primary">
                    {fmtPrice(ev.box_ev_usd)}
                  </div>
                </div>
              </div>
              {premium != null && (
                <div className="mt-3 flex items-center gap-2 text-xs">
                  {premium >= 0 ? (
                    <TrendingUp className="h-3.5 w-3.5 text-accent-red" />
                  ) : (
                    <TrendingDown className="h-3.5 w-3.5 text-accent-green" />
                  )}
                  <span
                    className={
                      premium >= 0 ? "text-accent-red" : "text-accent-green"
                    }
                  >
                    Sealed{" "}
                    {premium >= 0 ? "premium" : "discount"} of{" "}
                    <span className="font-bold">
                      {Math.abs(premium).toFixed(1)}%
                    </span>{" "}
                    vs Est. value
                  </span>
                </div>
              )}
              <p className="mt-3 text-[10px] leading-relaxed text-text-tertiary">
                Modeled from a modern-era pack composition (6 Common + 3
                Uncommon + 1 foil + 1 reverse holo) × the set&apos;s current
                average card prices. Real hits can swing the actual value
                either way.
              </p>
            </div>
          )}

          {product.description && (
            <div className="mt-6 text-sm text-text-secondary leading-relaxed whitespace-pre-line">
              {product.description}
            </div>
          )}
        </div>
      </div>

      <ProductPriceChart productId={product.id} />
      <ProductLiveListings productId={product.id} />

      {product.set_id && (
        <div className="mt-10">
          <Link
            href={`/sets/${product.set_id}`}
            className="text-sm text-text-secondary hover:text-text-primary underline decoration-dotted"
          >
            → All cards in {product.set_name}
          </Link>
        </div>
      )}
    </main>
  );
}
