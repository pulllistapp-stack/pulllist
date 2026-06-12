import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CardNeighborsNav } from "@/components/CardNeighborsNav";
import { CardThumb } from "@/components/CardThumb";
import { OwnedToggle } from "@/components/OwnedToggle";
import { PriceBreakdown } from "@/components/PriceBreakdown";
import { RarityChip } from "@/components/RarityChip";
import type { Card, CardNeighbors } from "@/lib/api";
import { getAlternates, getCard, getCardNeighbors } from "@/lib/api";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function CardDetailPage({ params }: Props) {
  const { id } = await params;

  let card: Card;
  try {
    card = await getCard(id);
  } catch (e) {
    if (e instanceof Error && e.message.includes("404")) notFound();
    throw e;
  }

  const [alternates, neighbors] = await Promise.all([
    getAlternates(id, 12).catch(() => [] as Card[]),
    getCardNeighbors(id).catch(
      () =>
        ({ prev: null, next: null, position: null, total: 0 }) as CardNeighbors,
    ),
  ]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <nav className="mb-8 text-sm text-text-secondary">
        <Link href="/" className="hover:text-text-primary">
          Home
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link href="/sets" className="hover:text-text-primary">
          Sets
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <Link
          href={`/sets/${card.set_id}`}
          className="hover:text-text-primary"
        >
          {card.set_name ?? card.set_id}
        </Link>
        <span className="mx-2 text-text-tertiary">/</span>
        <span className="text-text-primary">{card.name}</span>
      </nav>

      <CardNeighborsNav
        setId={card.set_id}
        setName={card.set_name}
        neighbors={neighbors}
      />

      <div className="grid md:grid-cols-[400px_1fr] gap-10 mb-16">
        <div className="flex justify-center md:justify-start">
          {card.image_large ? (
            <Image
              src={card.image_large}
              alt={card.name}
              width={400}
              height={557}
              className="rounded-lg w-full max-w-sm h-auto"
              unoptimized
              priority
            />
          ) : (
            <div className="aspect-[245/342] w-full max-w-sm rounded-lg bg-bg-surface border border-border flex items-center justify-center text-text-tertiary">
              no image
            </div>
          )}
        </div>

        <div className="flex flex-col">
          <div className="text-xs font-mono text-text-tertiary mb-1">
            #{card.number ?? "—"} ·{" "}
            <Link
              href={`/sets/${card.set_id}`}
              className="hover:text-text-primary"
            >
              {card.set_name ?? card.set_id}
            </Link>
          </div>
          <h1 className="text-4xl font-bold mb-4 tracking-tight">{card.name}</h1>

          <div className="mb-5">
            <OwnedToggle cardId={card.id} />
          </div>

          <div className="flex flex-wrap gap-2 mb-6">
            <RarityChip rarity={card.rarity} size="md" />
            {card.supertype && (
              <span className="inline-flex items-center rounded-chip bg-text-tertiary/15 text-text-secondary px-2.5 py-1 text-xs font-mono uppercase tracking-wider">
                {card.supertype}
              </span>
            )}
            {card.types?.map((t) => (
              <span
                key={t}
                className="inline-flex items-center rounded-chip bg-accent-yellow/15 text-accent-yellow px-2.5 py-1 text-xs font-mono uppercase tracking-wider"
              >
                {t}
              </span>
            ))}
            {card.subtypes?.map((st) => (
              <span
                key={st}
                className="inline-flex items-center rounded-chip bg-accent-blue/15 text-accent-blue px-2.5 py-1 text-xs font-mono uppercase tracking-wider"
              >
                {st}
              </span>
            ))}
          </div>

          {card.hp && (
            <div className="mb-4 text-sm">
              <span className="text-text-tertiary">HP </span>
              <span className="font-mono font-bold text-base">{card.hp}</span>
            </div>
          )}

          {card.flavor_text && (
            <p className="text-sm text-text-secondary italic border-l-2 border-border pl-4 mb-6">
              {card.flavor_text}
            </p>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
            <PriceBreakdown
              tcgplayerPrices={card.tcgplayer_prices}
              tcgplayerUrl={card.tcgplayer_url}
              searchCtx={{
                cardName: card.name,
                cardNumber: card.number,
                setName: card.set_name,
                setPrintedTotal: card.set_printed_total,
                setPtcgoCode: card.set_ptcgo_code,
              }}
            />
            {card.cardmarket_url && (
              <div className="rounded-card bg-bg-surface border border-border p-5">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-xs font-mono uppercase tracking-wider text-text-tertiary">
                    Cardmarket (EUR)
                  </div>
                  <a
                    href={card.cardmarket_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent-blue hover:underline"
                  >
                    View →
                  </a>
                </div>
                {card.cardmarket_prices?.trendPrice != null ? (
                  <div className="text-2xl font-bold font-mono text-accent-green">
                    €{Number(card.cardmarket_prices.trendPrice).toFixed(2)}
                    <span className="text-xs text-text-tertiary ml-2 font-normal">
                      trend
                    </span>
                  </div>
                ) : (
                  <div className="text-sm text-text-tertiary">
                    Browse for current EU listings.
                  </div>
                )}
              </div>
            )}
          </div>

          {card.artist && (
            <div className="text-xs text-text-tertiary">
              Illustrated by <span className="text-text-secondary">{card.artist}</span>
            </div>
          )}

          <div className="mt-8 rounded-card bg-accent-yellow/5 border border-accent-yellow/20 p-4 text-sm text-text-secondary">
            <span className="text-accent-yellow font-semibold">Coming next:</span>{" "}
            Price history chart (need a few days of snapshots), sealed-product
            source mapping (which ETB/Booster contains this), and live retailer
            stock.
          </div>
        </div>
      </div>

      {alternates.length > 0 && (
        <section className="mb-12">
          <h2 className="text-sm font-mono uppercase tracking-wider text-text-tertiary mb-4">
            Other versions of {card.name}
            <span className="text-text-tertiary"> · {alternates.length}</span>
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {alternates.map((c) => (
              <CardThumb key={c.id} card={c} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
