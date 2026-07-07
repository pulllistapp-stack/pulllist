"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "./AuthProvider";

const HIDE_FOOTER_ON = ["/scan"];

export function Footer() {
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  // Hide Login/Signup once the user is authenticated. While auth state is
  // still loading we also hide them — better to render the shorter list
  // briefly than to flash login links to a signed-in user.
  const showAuthLinks = !authLoading && !user;
  // Scan page is a focused, immersive surface — site-wide footer (marketplace
  // links, mascot, etc.) clutters the result panel below the camera frame.
  if (pathname && HIDE_FOOTER_ON.some((p) => pathname.startsWith(p))) {
    return null;
  }

  return (
    <footer className="mt-20 border-t border-border bg-bg-surface/40">
      <div className="mx-auto max-w-[100rem] px-4 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Link
              href="/"
              className="inline-block text-2xl font-extrabold tracking-tight"
            >
              <span className="text-text-primary">Pull</span>
              <span className="bg-gradient-to-r from-accent-yellow via-amber-400 to-teal-400 bg-clip-text text-transparent">
                List
              </span>
            </Link>
            <p className="mt-3 max-w-sm text-sm text-text-secondary">
              The Pokémon TCG catalog &amp; collection tracker. Real-time market data
              from TCGplayer and eBay — all in one place.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-tertiary">
              Catalog
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
                <Link href="/trending" className="text-text-secondary hover:text-text-primary">
                  Trending
                </Link>
              </li>
              <li>
                <Link href="/drops" className="text-text-secondary hover:text-text-primary">
                  Recent drops
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
                  href="/portfolio"
                  className="text-text-secondary hover:text-text-primary"
                >
                  Portfolio
                </Link>
              </li>
              <li>
                <Link
                  href="/wishlist"
                  className="text-text-secondary hover:text-text-primary"
                >
                  Wishlist
                </Link>
              </li>
              <li>
                <Link
                  href="/me/settings"
                  className="text-text-secondary hover:text-text-primary"
                >
                  Settings
                </Link>
              </li>
              {showAuthLinks && (
                <>
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
                </>
              )}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-tertiary">
              Company
            </h3>
            <ul className="mt-3 space-y-2 text-sm">
              <li>
                <Link href="/about" className="text-text-secondary hover:text-text-primary">
                  About
                </Link>
              </li>
              <li>
                <Link href="/pricing" className="text-text-secondary hover:text-text-primary">
                  Pricing
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="text-text-secondary hover:text-text-primary">
                  Privacy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="text-text-secondary hover:text-text-primary">
                  Terms
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className="text-text-secondary hover:text-text-primary"
                >
                  Contact
                </Link>
              </li>
              <li>
                <Link
                  href="/legal"
                  className="text-text-secondary hover:text-text-primary"
                >
                  Legal &amp; attributions
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Compact bottom bar. Full affiliate disclosure, attributions,
            and trademark notice live on /legal — linking them from
            here satisfies FTC "clear and conspicuous" + CC attribution
            requirements while keeping the footer clean. */}
        <div className="mt-10 border-t border-border pt-6 flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center text-xs text-text-tertiary">
          <p className="leading-relaxed">
            © {new Date().getFullYear()} PullList · Fan-built, unaffiliated with
            Nintendo / The Pokémon Company ·{" "}
            <Link
              href="/legal"
              className="underline decoration-dotted hover:text-text-secondary"
            >
              Affiliate &amp; attributions
            </Link>
          </p>
          <span className="inline-flex shrink-0 items-center gap-1.5 font-medium uppercase tracking-wider">
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
