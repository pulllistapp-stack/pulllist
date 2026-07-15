import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { InMyMasterSetsBadge } from "@/components/card/InMyMasterSetsBadge";
import { PullListCardDetail } from "@/components/card/PullListCardDetail";
import type { Card, CardHistory, CardNeighbors } from "@/lib/api";
import { getAlternates, getCard, getCardHistory, getCardNeighbors } from "@/lib/api";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

const SITE_URL = "https://www.pulllist.org";

function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "";
  if (v >= 1000) return `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return `$${v.toFixed(2)}`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  let card: Card;
  try {
    card = await getCard(id);
  } catch {
    return { title: "Card — PullList" };
  }

  const nameWithNumber = card.number
    ? `${card.name} ${card.number}${card.set_printed_total ? `/${card.set_printed_total}` : ""}`
    : card.name;
  const setPart = card.set_name ? ` (${card.set_name})` : "";
  const title = `${nameWithNumber}${setPart} — Sold + Live Prices | PullList`;

  const priceLine = card.market_price_usd
    ? `Market ${fmtPrice(card.market_price_usd)}`
    : "";

  const description =
    `${card.name}${card.set_name ? ` from ${card.set_name}` : ""}. ` +
    (priceLine ? `${priceLine}. ` : "") +
    `PSA / CGC / BGS / TAG sold-listing medians, live eBay listings, ` +
    `TCGplayer + Cardmarket prices, 90-day price history. Free on PullList.`;

  const canonical = `${SITE_URL}/cards/${card.id}`;
  const ogImage = card.image_large || card.image_small || undefined;

  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      type: "website",
      url: canonical,
      siteName: "PullList",
      images: ogImage ? [{ url: ogImage, alt: card.name }] : undefined,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ogImage ? [ogImage] : undefined,
    },
  };
}

/**
 * For each source, compute the latest price minus the value 7 days ago,
 * expressed as %. Used for the secondary-prices delta pills.
 */
function compute7dDelta(history: CardHistory | null, source: string): number | null {
  if (!history) return null;
  const series = Object.entries(history.series).find(([k]) => k.startsWith(source + ":"))?.[1];
  if (!series || series.length < 2) return null;
  const points = series.filter((p) => p.market != null).sort((a, b) => a.date.localeCompare(b.date));
  if (points.length < 2) return null;
  const latest = points[points.length - 1].market!;
  const oldest = points[0].market!;
  if (oldest <= 0) return null;
  return ((latest - oldest) / oldest) * 100;
}

function latestValue(history: CardHistory | null, source: string): number | null {
  if (!history) return null;
  const series = Object.entries(history.series).find(([k]) => k.startsWith(source + ":"))?.[1];
  if (!series?.length) return null;
  const points = series.filter((p) => p.market != null).sort((a, b) => a.date.localeCompare(b.date));
  return points[points.length - 1]?.market ?? null;
}

function sparklineSeries(history: CardHistory | null, source: string): number[] {
  if (!history) return [];
  const series = Object.entries(history.series).find(([k]) => k.startsWith(source + ":"))?.[1];
  if (!series) return [];
  return series
    .filter((p) => p.market != null)
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((p) => p.market as number);
}

export default async function CardDetailPage({ params }: Props) {
  const { id } = await params;

  let card: Card;
  try {
    card = await getCard(id);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  const [alternates, neighbors, history7d] = await Promise.all([
    getAlternates(id, 12).catch(() => [] as Card[]),
    getCardNeighbors(id).catch(
      () => ({ prev: null, next: null, position: null, total: 0 }) as CardNeighbors,
    ),
    getCardHistory(id, { days: 7 }).catch(() => null as CardHistory | null),
  ]);

  const initialEbayMedian = latestValue(history7d, "ebay");
  const ebayDelta7d = compute7dDelta(history7d, "ebay");
  const tcgDelta7d = compute7dDelta(history7d, "tcgplayer");
  const ebaySpark7d = sparklineSeries(history7d, "ebay");
  const tcgSpark7d = sparklineSeries(history7d, "tcgplayer");

  // Schema.org Product markup — lets Google display the card as a
  // rich result (price shown in search) instead of a plain title link.
  // Only emitted when we have a real market price to attach to `offers`.
  const productSchema: Record<string, unknown> | null = card.market_price_usd
    ? {
        "@context": "https://schema.org",
        "@type": "Product",
        name: card.number
          ? `${card.name} ${card.number}${card.set_printed_total ? `/${card.set_printed_total}` : ""}`
          : card.name,
        description: card.set_name
          ? `${card.name} from the ${card.set_name} Pokémon TCG set. Real sold + live listing prices, graded slabs across PSA / CGC / BGS / TAG.`
          : `${card.name} — Pokémon TCG card with live pricing on PullList.`,
        image: card.image_large || card.image_small || undefined,
        sku: card.id,
        brand: { "@type": "Brand", name: "Pokémon TCG" },
        category: card.rarity ?? "Trading Card",
        offers: {
          "@type": "Offer",
          priceCurrency: "USD",
          price: card.market_price_usd.toFixed(2),
          availability: "https://schema.org/InStock",
          url: `${SITE_URL}/cards/${card.id}`,
          seller: { "@type": "Organization", name: "PullList" },
        },
      }
    : null;

  return (
    <>
      {productSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(productSchema) }}
        />
      )}
      <PullListCardDetail
        card={card}
        alternates={alternates}
        neighbors={neighbors}
        initialEbayMedian={initialEbayMedian}
        ebayDelta7d={ebayDelta7d}
        tcgDelta7d={tcgDelta7d}
        ebaySpark7d={ebaySpark7d}
        tcgSpark7d={tcgSpark7d}
      />
      <div className="mx-auto max-w-6xl px-4 sm:px-6 -mt-4 mb-8">
        <InMyMasterSetsBadge
          cardId={card.id}
          setId={card.set_id}
          setName={card.set_name}
        />
      </div>
    </>
  );
}
