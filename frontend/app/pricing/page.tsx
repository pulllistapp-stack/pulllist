import Link from "next/link";
import { Metadata } from "next";
import { Check, Sparkles } from "lucide-react";

export const metadata: Metadata = {
  title: "Pricing · PullList",
  description:
    "PullList is free for collectors. We earn from affiliate links when you buy through TCGplayer or eBay — no paywall, no Pro tier.",
};

const FREE_FEATURES = [
  "Track every pull across 31,000+ indexed cards in EN / JP / KR",
  "Live prices from TCGplayer and eBay",
  "1-year price history with weekly density",
  "Wishlist with price targets",
  "Public portfolio sharing with one-click OG card",
  "CSV export of your collection",
  "Daily portfolio value snapshots",
  "Camera scan to identify cards",
];

export default function PricingPage() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <header className="text-center mb-12">
        <p className="font-mono text-xs uppercase tracking-widest text-text-tertiary">
          Pricing
        </p>
        <h1 className="mt-2 text-4xl sm:text-5xl font-extrabold tracking-tight text-text-primary">
          Free forever.
        </h1>
        <p className="mt-3 text-text-secondary max-w-xl mx-auto">
          We make money when you click through to TCGplayer or eBay to buy a
          card. That&apos;s it. No tiers, no paywall, no &quot;upgrade to see
          this chart&quot; nonsense.
        </p>
      </header>

      <section className="rounded-3xl border-2 border-accent-yellow/60 bg-bg-surface p-8 shadow-lg shadow-accent-yellow/10 relative">
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-accent-yellow text-gray-900 text-xs font-bold tracking-wider uppercase shadow-md shadow-accent-yellow/30 inline-flex items-center gap-1">
          <Sparkles className="h-3 w-3" />
          The only plan
        </div>

        <div className="text-center mt-2 mb-6">
          <p className="text-5xl font-extrabold text-text-primary">$0</p>
          <p className="mt-1 text-sm text-text-secondary">
            per month, per year, per anything.
          </p>
        </div>

        <ul className="space-y-3">
          {FREE_FEATURES.map((feat) => (
            <li key={feat} className="flex items-start gap-3 text-sm">
              <Check className="h-4 w-4 text-accent-green flex-shrink-0 mt-0.5" />
              <span className="text-text-primary">{feat}</span>
            </li>
          ))}
        </ul>

        <Link
          href="/signup"
          className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent-yellow text-gray-900 font-bold py-3 text-sm hover:brightness-105 shadow-md shadow-accent-yellow/30 transition-all"
        >
          Start collecting — free
          <span aria-hidden>→</span>
        </Link>
      </section>

      <section className="mt-10 rounded-2xl border border-border bg-bg-surface p-6">
        <h2 className="text-sm font-mono uppercase tracking-widest text-text-tertiary mb-3">
          How it works
        </h2>
        <p className="text-sm text-text-secondary">
          When the &quot;Buy on TCGplayer&quot; or &quot;Buy on eBay&quot;
          button on a card&apos;s page sends you to checkout and you buy
          something, the retailer pays us a small percentage. The price you
          pay is exactly the same as if you went there directly. Links marked
          <span className="mx-1 inline-block font-mono text-[10px] bg-text-tertiary/15 text-text-tertiary px-1.5 py-0.5 rounded-sm align-middle">
            Ad
          </span>
          are affiliate links - FTC disclosure.
        </p>
      </section>

      <footer className="mt-10 text-center text-xs text-text-tertiary font-mono uppercase tracking-widest">
        <div className="flex items-center justify-center gap-4">
          <Link href="/about" className="hover:text-text-secondary">
            About
          </Link>
          <span aria-hidden>·</span>
          <Link href="/privacy" className="hover:text-text-secondary">
            Privacy
          </Link>
          <span aria-hidden>·</span>
          <Link href="/terms" className="hover:text-text-secondary">
            Terms
          </Link>
        </div>
      </footer>
    </main>
  );
}
