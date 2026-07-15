import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Box } from "lucide-react";

import { getSeries, SeriesProductPayload, SeriesSetPayload } from "@/lib/api";

export const dynamic = "force-dynamic";

const SITE_URL = "https://www.pulllist.org";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  let data;
  try {
    data = await getSeries(slug);
  } catch {
    return { title: "Series — PullList" };
  }

  const title = `${data.series} Card Prices & Sealed Products | PullList`;
  const description =
    `Live prices for every card in the ${data.series} Pokémon TCG era — ` +
    `${data.card_count.toLocaleString()} cards across ${data.set_count} sets, ` +
    `${data.product_count} sealed products tracked. Real PSA/CGC/BGS/TAG sold ` +
    `medians, live eBay listings, TCGplayer prices, sealed EV calculators.`;

  return {
    title,
    description,
    alternates: { canonical: `${SITE_URL}/series/${slug}` },
    openGraph: {
      title,
      description,
      type: "website",
      url: `${SITE_URL}/series/${slug}`,
      siteName: "PullList",
    },
    twitter: { card: "summary_large_image", title, description },
  };
}

const TYPE_LABEL: Record<string, string> = {
  booster_box: "Booster Box",
  etb: "Elite Trainer Box",
  booster_bundle: "Bundle",
  premium_collection: "Premium",
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

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function SeriesPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let data;
  try {
    data = await getSeries(slug);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  return (
    <main className="mx-auto max-w-[100rem] px-4 py-8">
      <nav className="mb-6 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/sets" className="hover:text-text-primary">
          Sets
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">{data.series}</span>
      </nav>

      <header className="mb-8 rounded-card border border-border bg-bg-surface/70 p-6">
        <div className="mb-2 text-[10px] font-mono uppercase tracking-widest text-text-tertiary">
          Series
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight md:text-4xl">
          {data.series}
        </h1>
        <div className="mt-5 flex flex-wrap gap-8">
          <Stat label="Sets" value={data.set_count} />
          <Stat label="Cards" value={data.card_count} />
          <Stat label="Sealed products" value={data.product_count} />
        </div>
      </header>

      <section className="mb-10">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-lg font-bold tracking-tight">Sets</h2>
          <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
            {data.set_count} in this era
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {data.sets.map((s) => (
            <SetTile key={s.id} set={s} />
          ))}
        </div>
      </section>

      {data.products.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-lg font-bold tracking-tight">Sealed products</h2>
            <div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
              {data.product_count} across the era
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {data.products.map((p) => (
              <ProductTile key={p.id} product={p} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-2xl font-extrabold text-text-primary">
        {value.toLocaleString()}
      </div>
      <div className="mt-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
        {label}
      </div>
    </div>
  );
}

function SetTile({ set }: { set: SeriesSetPayload }) {
  return (
    <Link
      href={`/sets/${set.id}`}
      className="group flex items-center gap-4 rounded-card border border-border bg-bg-surface p-4 transition-colors hover:border-accent-yellow/40"
    >
      <div className="relative h-16 w-24 flex-shrink-0">
        {set.logo_url ? (
          <Image
            src={set.logo_url}
            alt={set.name}
            fill
            className="object-contain"
            sizes="96px"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-text-tertiary">
            no logo
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-bold text-text-primary group-hover:text-accent-yellow">
          {set.name}
        </div>
        <div className="mt-0.5 text-xs text-text-tertiary">
          {fmtDate(set.release_date)}
        </div>
        <div className="mt-1 font-mono text-xs text-text-secondary">
          <span className="text-accent-yellow">{set.card_count}</span>
          <span className="text-text-tertiary">
            /
            {set.total ?? set.printed_total ?? "?"} cards
          </span>
        </div>
      </div>
    </Link>
  );
}

function ProductTile({ product }: { product: SeriesProductPayload }) {
  return (
    <Link
      href={`/products/${product.id}`}
      className="group overflow-hidden rounded-card border border-border bg-bg-surface transition-colors hover:border-accent-yellow/40"
    >
      <div className="relative aspect-[3/4] bg-bg">
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.name}
            fill
            className="object-contain p-2"
            sizes="(max-width: 640px) 50vw, (max-width: 1024px) 25vw, 15vw"
            unoptimized
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-text-tertiary">
            No image
          </div>
        )}
      </div>
      <div className="p-2">
        <div className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
          <Box className="h-3 w-3" />
          {TYPE_LABEL[product.product_type] ?? product.product_type}
        </div>
        <div className="mt-1 line-clamp-2 text-xs font-semibold text-text-primary">
          {product.name}
        </div>
        <div className="mt-1 font-mono text-xs text-accent-green">
          {fmtPrice(product.market_price_usd)}
        </div>
      </div>
    </Link>
  );
}
