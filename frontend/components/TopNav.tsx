"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "./AuthProvider";
import { SearchBar } from "./SearchBar";

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
          className="flex items-center gap-2 flex-shrink-0 hover:opacity-90"
        >
          <span className="relative h-9 w-9 overflow-hidden rounded-full ring-2 ring-amber-300/60 bg-amber-100">
            <Image
              src="/pullist-mascot.png"
              alt="PullList mascot"
              fill
              className="object-cover"
              sizes="36px"
              priority
              unoptimized
            />
          </span>
          <span className="text-xl font-bold tracking-tight">
            Pull<span className="text-accent-yellow">List</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-5 text-sm text-text-secondary">
          <Link href="/sets" className="hover:text-text-primary">
            Sets
          </Link>
          <Link href="/cards" className="hover:text-text-primary">
            Cards
          </Link>
          <Link href="/drops" className="hover:text-text-primary">
            Drops
          </Link>
          <Link href="/pricing" className="hover:text-text-primary">
            Pricing
          </Link>
        </nav>

        <div className="flex-1 flex justify-center min-w-0">
          <SearchBar compact />
        </div>

        {/* Desktop auth area */}
        <div className="hidden md:flex items-center gap-3 text-sm flex-shrink-0">
          {loading ? (
            <span className="text-text-tertiary">…</span>
          ) : user ? (
            <>
              <Link
                href="/me/collection"
                className="text-text-secondary hover:text-text-primary"
              >
                My Collection
              </Link>
              <span className="text-text-tertiary">·</span>
              <span
                className="text-text-primary truncate max-w-[120px]"
                title={user.email}
              >
                {user.name ?? user.email.split("@")[0]}
              </span>
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
                className="rounded-btn bg-accent-yellow px-3 py-1.5 text-bg font-medium hover:brightness-110"
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
            <MobileLink href="/drops">Drops</MobileLink>
            <MobileLink href="/pricing">Pricing</MobileLink>

            <div className="h-px bg-border my-3" />

            {loading ? (
              <span className="px-3 py-2 text-text-tertiary">…</span>
            ) : user ? (
              <>
                <MobileLink href="/me/collection">My Collection</MobileLink>
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
                  className="flex-1 rounded-btn bg-accent-yellow px-3 py-2 text-center text-bg font-medium hover:brightness-110"
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
