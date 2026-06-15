"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanLine } from "lucide-react";

import { useAuth } from "./AuthProvider";

/**
 * Floating Action Button for "Scan a card". Pinned bottom-right so it's
 * always reachable in PWA standalone mode where the top nav can feel far.
 * Hidden on the /scan page itself and on auth pages.
 */
export function ScanFAB() {
  const { user } = useAuth();
  const pathname = usePathname();

  if (!user) return null;
  if (!pathname) return null;
  if (pathname.startsWith("/scan")) return null;
  if (pathname.startsWith("/login") || pathname.startsWith("/signup")) return null;
  // Card detail page has its own bottom CTAs (Buy on TCGplayer, sticky
  // owned button) — the FAB overlaps them awkwardly on mobile.
  if (pathname.startsWith("/cards/")) return null;

  return (
    <Link
      href="/scan"
      aria-label="Scan a card"
      title="Scan a card"
      className="
        fixed bottom-5 right-5 sm:bottom-7 sm:right-7 z-40
        inline-flex h-14 w-14 sm:h-15 sm:w-15 items-center justify-center
        rounded-full
        bg-accent-yellow text-gray-900
        shadow-xl shadow-accent-yellow/40
        ring-2 ring-white/10
        hover:scale-110 active:scale-95
        transition-transform duration-150
      "
    >
      <ScanLine className="h-6 w-6" />
      <span className="sr-only">Scan a card</span>
    </Link>
  );
}
