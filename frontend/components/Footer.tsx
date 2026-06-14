import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-20 border-t border-border bg-bg-surface/40">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Link href="/" className="inline-block">
              <span className="relative block h-10 w-[140px]">
                <Image
                  src="/pullist-mascot.png"
                  alt="PullList"
                  fill
                  className="object-contain object-left"
                  sizes="140px"
                  unoptimized
                />
              </span>
            </Link>
            <p className="mt-3 max-w-sm text-sm text-text-secondary">
              The Pokémon TCG catalog &amp; collection tracker. Real-time market data
              from TCGplayer, Cardmarket, and eBay — all in one place.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-tertiary">
              Marketplace
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link href="/sets" className="text-text-secondary hover:text-text-primary">
                  Browse sets
                </Link>
              </li>
              <li>
                <Link href="/cards" className="text-text-secondary hover:text-text-primary">
                  All cards
                </Link>
              </li>
              <li>
                <Link href="/drops" className="text-text-secondary hover:text-text-primary">
                  Recent drops
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="text-text-secondary hover:text-text-primary">
                  Pricing trends
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-tertiary">
              Account
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link
                  href="/me/collection"
                  className="text-text-secondary hover:text-text-primary"
                >
                  My collection
                </Link>
              </li>
              <li>
                <Link href="/login" className="text-text-secondary hover:text-text-primary">
                  Login
                </Link>
              </li>
              <li>
                <Link href="/signup" className="text-text-secondary hover:text-text-primary">
                  Sign up
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-border pt-6 text-xs text-text-tertiary sm:flex-row sm:items-center">
          <p>
            © {new Date().getFullYear()} PullList. Not affiliated with Nintendo, Creatures,
            or GAME FREAK.
          </p>
          <span className="inline-flex items-center gap-1.5 font-medium uppercase tracking-wider">
            <span className="relative inline-flex h-2 w-2">
              <span className="absolute inset-0 inline-flex animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Systems operational
          </span>
        </div>
      </div>
    </footer>
  );
}
