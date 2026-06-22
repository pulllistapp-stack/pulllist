"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { SearchBar } from "./SearchBar";

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = resolvedTheme === "dark";
  return (
    <button
      aria-label="Toggle theme"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border text-text-secondary transition-colors hover:text-text-primary hover:border-accent-yellow/40"
    >
      {mounted && isDark ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}

export function TopNav() {
  const { user, loading, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  // Close drawer on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-bg/80 border-b border-border">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-16 flex items-center gap-3 sm:gap-6">
        <Link
          href="/"
          className="flex items-center flex-shrink-0 hover:opacity-90"
          aria-label="PullList home"
        >
          <span className="relative block h-10 w-[140px] sm:h-12 sm:w-[170px]">
            <Image
              src="/pullist-mascot-logo.png"
              alt="PullList"
              fill
              className="object-contain object-left"
              sizes="(max-width: 640px) 140px, 170px"
              priority
              unoptimized
            />
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-5 text-sm text-text-secondary">
          <Link href="/sets" className="hover:text-text-primary">
            Sets
          </Link>
          <Link href="/cards" className="hover:text-text-primary">
            Cards
          </Link>
          <Link href="/trending" className="hover:text-text-primary">
            Trending
          </Link>
          <Link href="/drops" className="hover:text-text-primary">
            Drops
          </Link>
          <Link href="/news" className="hover:text-text-primary">
            News
          </Link>
          <Link href="/pricing" className="hover:text-text-primary">
            Pricing
          </Link>
        </nav>

        <div className="flex-1 flex justify-center min-w-0">
          <SearchBar compact />
        </div>

        {/* Theme toggle — always visible (desktop + mobile) */}
        <div className="flex-shrink-0 flex items-center gap-1.5">
          <ThemeToggle />
        </div>

        {/* Desktop auth area */}
        <div className="hidden md:flex items-center gap-3 text-sm flex-shrink-0">
          {loading ? (
            <span className="text-text-tertiary">…</span>
          ) : user ? (
            <>
              <Link
                href="/wishlist"
                className="text-text-secondary hover:text-text-primary"
              >
                Wishlist
              </Link>
              <Link
                href="/portfolio"
                className="text-text-secondary hover:text-text-primary"
              >
                Portfolio
              </Link>
              <span className="text-text-tertiary">·</span>
              <Link
                href="/me/settings"
                className="text-text-primary truncate max-w-[120px] hover:text-accent-yellow transition-colors"
                title={`${user.email} - Settings`}
              >
                {user.name ?? user.email.split("@")[0]}
              </Link>
              <button
                onClick={logout}
                className="text-text-secondary hover:text-text-primary"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="text-text-secondary hover:text-text-primary"
              >
                Login
              </Link>
              <Link
                href="/signup"
                className="rounded-btn bg-accent-yellow px-3 py-1.5 text-gray-900 font-semibold hover:brightness-110"
              >
                Sign up
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setMobileOpen((v) => !v)}
          className="md:hidden flex-shrink-0 rounded-btn border border-border p-2 text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
          aria-label="Toggle menu"
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <CloseIcon /> : <MenuIcon />}
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-bg">
          <nav className="mx-auto max-w-7xl px-4 sm:px-6 py-4 flex flex-col gap-1 text-sm">
            <MobileLink href="/sets">Browse sets</MobileLink>
            <MobileLink href="/cards">Browse cards</MobileLink>
            <MobileLink href="/trending">Trending</MobileLink>
            <MobileLink href="/drops">Drops</MobileLink>
            <MobileLink href="/pricing">Pricing</MobileLink>

            <div className="h-px bg-border my-3" />

            {loading ? (
              <span className="px-3 py-2 text-text-tertiary">…</span>
            ) : user ? (
              <>
                <MobileLink href="/scan">📸 Scan a card</MobileLink>
                <MobileLink href="/wishlist">Wishlist</MobileLink>
                <MobileLink href="/portfolio">Portfolio</MobileLink>
                <MobileLink href="/me/settings">Settings</MobileLink>
                <div className="px-3 py-2 text-xs text-text-tertiary font-mono truncate">
                  Logged in as {user.name ?? user.email}
                </div>
                <button
                  onClick={() => {
                    logout();
                    setMobileOpen(false);
                  }}
                  className="rounded-btn px-3 py-2 text-left text-text-secondary hover:text-text-primary hover:bg-bg-surface"
                >
                  Logout
                </button>
              </>
            ) : (
              <div className="flex gap-2 mt-1">
                <Link
                  href="/login"
                  className="flex-1 rounded-btn border border-border px-3 py-2 text-center text-text-secondary hover:text-text-primary hover:border-accent-yellow/40"
                >
                  Login
                </Link>
                <Link
                  href="/signup"
                  className="flex-1 rounded-btn bg-accent-yellow px-3 py-2 text-center text-gray-900 font-semibold hover:brightness-110"
                >
                  Sign up
                </Link>
              </div>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}

function MobileLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className="rounded-btn px-3 py-2 text-text-secondary hover:text-text-primary hover:bg-bg-surface"
    >
      {children}
    </Link>
  );
}

function MenuIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="6" y1="6" x2="18" y2="18" />
      <line x1="6" y1="18" x2="18" y2="6" />
    </svg>
  );
}
