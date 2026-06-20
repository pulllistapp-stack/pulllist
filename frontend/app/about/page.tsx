import Image from "next/image";
import Link from "next/link";
import { Metadata } from "next";
import { Database, Heart, Search, Share2 } from "lucide-react";

export const metadata: Metadata = {
  title: "About · PullList",
  description:
    "PullList is a free, open Pokémon TCG catalog and collection tracker built for collectors who want clear prices and a quiet UI.",
};

const FEATURES = [
  {
    icon: Database,
    title: "Every set indexed",
    body: "12,000+ cards across every Pokémon TCG set, live prices from TCGplayer, eBay, and Cardmarket.",
  },
  {
    icon: Search,
    title: "Daily price history",
    body: "Backfilled 1Y price history per variant, updated daily. No paywall on the chart.",
  },
  {
    icon: Heart,
    title: "Collection + wishlist",
    body: "Track every pull. Watch the cards you want. Set price targets, see when the market gets close.",
  },
  {
    icon: Share2,
    title: "Public portfolios",
    body: "One-click share. Show off your vault with a clean OG card that previews on every platform.",
  },
];

export default function AboutPage() {
  return (
    <main className="max-w-4xl mx-auto px-4 py-12">
      <header className="flex flex-col sm:flex-row items-center gap-6 mb-10">
        <div className="h-24 w-24 rounded-full bg-white shadow-md flex items-center justify-center flex-shrink-0">
          <Image
            src="/pullist-mascot.png"
            alt="PullList mascot"
            width={80}
            height={80}
            className="object-contain"
            unoptimized
          />
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
            About
          </p>
          <h1 className="mt-1 text-3xl sm:text-4xl font-extrabold tracking-tight text-text-primary">
            Pokémon TCG, but quiet.
          </h1>
          <p className="mt-2 text-sm text-text-secondary max-w-xl">
            PullList is a free catalog and collection tracker built for
            collectors who want clear prices, real history, and a UI that
            doesn&apos;t scream at them.
          </p>
        </div>
      </header>

      <section className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-12">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-2xl border border-border bg-bg-surface p-5"
          >
            <div className="h-9 w-9 rounded-btn bg-accent-yellow/15 flex items-center justify-center mb-3">
              <Icon className="h-4 w-4 text-accent-yellow" />
            </div>
            <h2 className="font-semibold text-text-primary">{title}</h2>
            <p className="mt-1 text-sm text-text-secondary">{body}</p>
          </div>
        ))}
      </section>

      <section className="rounded-2xl border border-border bg-bg-surface p-6 mb-8">
        <h2 className="text-sm font-mono uppercase tracking-widest text-text-tertiary mb-3">
          How we make money
        </h2>
        <p className="text-sm text-text-secondary">
          PullList is free and stays free for collectors. When you click
          &quot;Buy on TCGplayer&quot; or &quot;Buy on eBay&quot; we earn a
          small commission through affiliate programs (TCGplayer Impact, eBay
          Partner Network). It costs you nothing, and it keeps the site running.
          Links marked <span className="font-mono text-[10px] bg-text-tertiary/15 text-text-tertiary px-1.5 py-0.5 rounded-sm">Ad</span> are affiliate
          links - FTC compliance disclosure.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-bg-surface p-6">
        <h2 className="text-sm font-mono uppercase tracking-widest text-text-tertiary mb-3">
          Data sources &amp; attributions
        </h2>
        <ul className="text-sm text-text-secondary space-y-2">
          <li>
            <strong className="text-text-primary">English card catalog:</strong>{" "}
            <a
              href="https://pokemontcg.io"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-text-primary"
            >
              pokemontcg.io
            </a>{" "}
            (CC BY 4.0)
          </li>
          <li>
            <strong className="text-text-primary">Japanese card catalog:</strong>{" "}
            <a
              href="https://tcgdex.net"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-text-primary"
            >
              TCGdex
            </a>{" "}
            — see their site for license terms
          </li>
          <li>
            <strong className="text-text-primary">JP card images (gap-fill):</strong>{" "}
            <a
              href="https://limitlesstcg.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-text-primary"
            >
              Limitless TCG
            </a>{" "}
            — used for sets and promos where TCGdex has metadata only
          </li>
          <li>
            <strong className="text-text-primary">Set logos:</strong>{" "}
            <a
              href="https://bulbapedia.bulbagarden.net"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-text-primary"
            >
              Bulbapedia / Bulbagarden Archives
            </a>{" "}
            (CC BY-NC-SA 2.5)
          </li>
          <li>
            <strong className="text-text-primary">TCGplayer prices:</strong>{" "}
            public infinite-api history endpoint
          </li>
          <li>
            <strong className="text-text-primary">eBay listings &amp; prices:</strong>{" "}
            <a
              href="https://developer.ebay.com/develop/get-started/getting-started"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-text-primary"
            >
              eBay Browse API
            </a>
          </li>
          <li>
            <strong className="text-text-primary">Cardmarket prices:</strong>{" "}
            pokemontcg.io aggregated trend data
          </li>
        </ul>
        <p className="mt-4 text-xs text-text-tertiary leading-relaxed">
          Card and set names are used for identification only (nominative fair
          use). Card images are displayed via the licensed APIs above or under
          fair-use thumbnail conventions. If you&apos;re a rights holder and
          believe content here needs to come down,{" "}
          <a
            href="mailto:hello@pulllist.org"
            className="underline hover:text-text-secondary"
          >
            email us
          </a>{" "}
          and we&apos;ll act on it within 48 hours.
        </p>
      </section>

      <footer className="mt-12 text-center text-xs text-text-tertiary font-mono uppercase tracking-widest leading-relaxed">
        Pokémon and all related characters are trademarks of Nintendo, Creatures
        Inc., GAME FREAK inc., and The Pokémon Company International. Wizards of
        the Coast owns trademarks on older Pokémon TCG sets. PullList is
        unaffiliated with, not endorsed by, and not sponsored by any of these
        companies.
        <div className="mt-3 flex items-center justify-center gap-4">
          <Link href="/privacy" className="hover:text-text-secondary">
            Privacy
          </Link>
          <span aria-hidden>·</span>
          <Link href="/terms" className="hover:text-text-secondary">
            Terms
          </Link>
          <span aria-hidden>·</span>
          <Link href="/pricing" className="hover:text-text-secondary">
            Pricing
          </Link>
        </div>
      </footer>
    </main>
  );
}
