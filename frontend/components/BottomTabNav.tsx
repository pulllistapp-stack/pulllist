"use client";

import { Heart, Layers, ScanLine, User, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "./AuthProvider";

/**
 * Mobile bottom tab bar. Sits under every screen except the immersive
 * scan camera and the auth pages. Center tab (Scan) is an elevated FAB —
 * it replaces the standalone ScanFAB.
 *
 * The card-detail page has its own sticky buy/own CTAs; hiding the tab
 * bar there keeps the CTA reachable without a z-index dance.
 */

const HIDE_ON = ["/scan", "/login", "/signup"];
const HIDE_PREFIXES = ["/cards/"];

export function BottomTabNav() {
  const pathname = usePathname();
  const { user } = useAuth();

  if (!pathname) return null;
  if (HIDE_ON.some((p) => pathname === p || pathname.startsWith(p + "/"))) return null;
  if (HIDE_PREFIXES.some((p) => pathname.startsWith(p))) return null;

  const meHref = user ? "/me/settings" : "/login";
  const meLabel = user ? "Me" : "Sign in";
  const meMatch = user ? "/me" : "/login";

  return (
    <>
      {/* In-flow spacer so page content clears the fixed nav. Kept
          alongside the nav itself so pages that hide the nav (scan,
          auth, card detail) don't inherit dead padding. */}
      <div
        aria-hidden
        className="md:hidden h-[calc(4.5rem_+_env(safe-area-inset-bottom))]"
      />
      <nav
        aria-label="Primary"
        className="
          fixed bottom-0 left-0 right-0 z-40 md:hidden
          border-t border-border bg-bg/95 backdrop-blur-md
          pb-[env(safe-area-inset-bottom)]
          pl-[env(safe-area-inset-left)]
          pr-[env(safe-area-inset-right)]
        "
      >
      <ul className="grid grid-cols-5 items-end h-16">
        <Tab
          href="/sets"
          label="Sets"
          icon={<Layers className="h-5 w-5" />}
          pathname={pathname}
        />
        <Tab
          href="/portfolio"
          label="Portfolio"
          icon={<Wallet className="h-5 w-5" />}
          pathname={pathname}
        />
        <ScanTab />
        <Tab
          href="/wishlist"
          label="Wishlist"
          icon={<Heart className="h-5 w-5" />}
          pathname={pathname}
        />
        <Tab
          href={meHref}
          label={meLabel}
          icon={<User className="h-5 w-5" />}
          pathname={pathname}
          matchOn={meMatch}
        />
      </ul>
    </nav>
    </>
  );
}

function Tab({
  href,
  label,
  icon,
  pathname,
  matchOn,
}: {
  href: string;
  label: string;
  icon: ReactNode;
  pathname: string;
  matchOn?: string;
}) {
  const match = matchOn ?? href;
  const active = pathname === match || pathname.startsWith(match + "/");
  return (
    <li className="flex">
      <Link
        href={href}
        aria-current={active ? "page" : undefined}
        className={`
          flex flex-1 flex-col items-center justify-center gap-1 py-2
          text-[10px] font-semibold tracking-tight
          transition-colors
          ${
            active
              ? "text-accent-yellow"
              : "text-text-tertiary hover:text-text-primary"
          }
        `}
      >
        {icon}
        <span>{label}</span>
      </Link>
    </li>
  );
}

function ScanTab() {
  return (
    <li className="flex justify-center">
      <Link
        href="/scan"
        aria-label="Scan a card"
        title="Scan a card"
        className="
          -mt-6 relative
          inline-flex h-14 w-14 items-center justify-center
          rounded-full
          bg-accent-yellow text-gray-900
          shadow-xl shadow-accent-yellow/40
          ring-4 ring-bg
          hover:scale-105 active:scale-95
          transition-transform duration-150
        "
      >
        <ScanLine className="h-6 w-6" />
      </Link>
    </li>
  );
}
