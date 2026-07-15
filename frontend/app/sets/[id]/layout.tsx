import type { Metadata } from "next";
import type { ReactNode } from "react";

import { getSet } from "@/lib/api";

const SITE_URL = "https://www.pulllist.org";

async function fetchSetForSeo(id: string) {
  try {
    return await getSet(id);
  } catch {
    return null;
  }
}

// Server-side metadata for the (client-rendered) set detail page.
// Wrapping the client page in this layout is the standard Next.js
// pattern for injecting SEO metadata into "use client" routes.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const set = await fetchSetForSeo(id);
  if (!set) return { title: "Set — PullList" };

  const priceLine =
    set.total_value_usd && set.card_count
      ? `Complete set value ~$${Math.round(set.total_value_usd).toLocaleString()} (${set.card_count} cards). `
      : "";

  const title = `${set.name} Cards, Prices & Sealed Products | PullList`;
  const description =
    `Every card in ${set.name}${set.series ? ` (${set.series})` : ""}. ` +
    priceLine +
    `Live PSA/CGC/BGS/TAG sold-listing medians, eBay + TCGplayer prices, ` +
    `sealed booster boxes / ETBs with EV calculators. Free on PullList.`;

  const canonical = `${SITE_URL}/sets/${set.id}`;
  const ogImage = set.logo_url || set.symbol_url || undefined;

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
      images: ogImage ? [{ url: ogImage, alt: set.name }] : undefined,
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ogImage ? [ogImage] : undefined,
    },
  };
}

// Layout does the second SEO job the client page can't: inject a
// CollectionPage JSON-LD script into the DOM so Google can read the
// structured summary of this set. Duplicates the getSet call from
// generateMetadata but both run on the server during the same render
// so it's one extra fetch, not user-facing latency.
export default async function SetLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const set = await fetchSetForSeo(id);

  const schema = set
    ? {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: set.name,
        description: `${set.name} Pokémon TCG cards, prices, and sealed products`,
        url: `${SITE_URL}/sets/${set.id}`,
        isPartOf: { "@type": "WebSite", name: "PullList", url: SITE_URL },
        ...(set.card_count
          ? {
              mainEntity: {
                "@type": "ItemList",
                numberOfItems: set.card_count,
                name: `${set.name} card list`,
              },
            }
          : {}),
      }
    : null;

  return (
    <>
      {schema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
      )}
      {children}
    </>
  );
}
