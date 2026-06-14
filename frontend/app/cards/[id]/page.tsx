import { notFound } from "next/navigation";

import { PullListCardDetail } from "@/components/card/PullListCardDetail";
import type { Card, CardHistory, CardNeighbors } from "@/lib/api";
import { getAlternates, getCard, getCardHistory, getCardNeighbors } from "@/lib/api";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

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
  const cardmarketDelta7d = compute7dDelta(history7d, "cardmarket");
  const ebaySpark7d = sparklineSeries(history7d, "ebay");
  const tcgSpark7d = sparklineSeries(history7d, "tcgplayer");
  const cardmarketSpark7d = sparklineSeries(history7d, "cardmarket");

  return (
    <PullListCardDetail
      card={card}
      alternates={alternates}
      neighbors={neighbors}
      initialEbayMedian={initialEbayMedian}
      ebayDelta7d={ebayDelta7d}
      tcgDelta7d={tcgDelta7d}
      cardmarketDelta7d={cardmarketDelta7d}
      ebaySpark7d={ebaySpark7d}
      tcgSpark7d={tcgSpark7d}
      cardmarketSpark7d={cardmarketSpark7d}
    />
  );
}
