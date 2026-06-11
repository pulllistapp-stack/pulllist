"use client";

import Link from "next/link";

import { useAuth } from "./AuthProvider";
import { SearchBar } from "./SearchBar";

export function TopNav() {
  const { user, loading, logout } = useAuth();

  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-bg/80 border-b border-border">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center gap-6">
        <Link
          href="/"
          className="text-xl font-bold tracking-tight flex-shrink-0 hover:opacity-90"
        >
          Pull<span className="text-accent-yellow">List</span>
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
              <span className="text-text-primary truncate max-w-[120px]" title={user.email}>
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
      </div>
    </header>
  );
}
