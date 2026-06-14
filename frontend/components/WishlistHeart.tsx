"use client";

import Link from "next/link";
import { useState } from "react";
import { Heart } from "lucide-react";

import { useAuth } from "./AuthProvider";
import { useWishlist } from "./WishlistProvider";
import { cn } from "@/lib/utils";

type Props = {
  cardId: string;
  /**
   * "corner" = small floating badge for card grids (absolute positioned).
   * "inline" = standalone button for the card detail page CTA row.
   */
  variant?: "corner" | "inline";
};

/**
 * Heart toggle. Filled rose when wishlisted, outline when not. Stops event
 * propagation so it works inside an outer <Link> (CardThumb wraps the whole
 * tile in a card-detail link).
 */
export function WishlistHeart({ cardId, variant = "corner" }: Props) {
  const { user } = useAuth();
  const { has, toggle } = useWishlist();
  const [pending, setPending] = useState(false);

  // Not logged in → click sends you to login. Display as outline (looks the
  // same as the empty state for a logged-in user).
  if (!user) {
    if (variant === "inline") {
      return (
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:border-rose-400/40 hover:text-rose-500 transition-colors"
        >
          <Heart className="h-3.5 w-3.5" />
          Log in to wishlist
        </Link>
      );
    }
    return (
      <Link
        href="/login"
        onClick={(e) => e.stopPropagation()}
        className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-bg/80 backdrop-blur-sm text-text-tertiary hover:text-rose-500 hover:bg-bg shadow-sm ring-1 ring-border transition-colors"
        title="Log in to wishlist"
        aria-label="Log in to wishlist"
      >
        <Heart className="h-3.5 w-3.5" />
      </Link>
    );
  }

  const wishlisted = has(cardId);

  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (pending) return;
    setPending(true);
    try {
      await toggle(cardId);
    } finally {
      setPending(false);
    }
  };

  if (variant === "inline") {
    return (
      <button
        onClick={onClick}
        disabled={pending}
        aria-pressed={wishlisted}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-all",
          "disabled:opacity-60 disabled:cursor-not-allowed",
          wishlisted
            ? "bg-rose-500/15 text-rose-500 border border-rose-500/40 hover:bg-rose-500/20"
            : "border border-border bg-bg-surface text-text-secondary hover:border-rose-400/40 hover:text-rose-500",
        )}
      >
        <Heart
          className={cn("h-3.5 w-3.5", wishlisted && "fill-current")}
        />
        {wishlisted ? "On wishlist" : "Wishlist"}
      </button>
    );
  }

  // Corner badge (default) — sits in top-right of CardThumb
  return (
    <button
      onClick={onClick}
      disabled={pending}
      aria-pressed={wishlisted}
      aria-label={wishlisted ? "Remove from wishlist" : "Add to wishlist"}
      title={wishlisted ? "Remove from wishlist" : "Add to wishlist"}
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-full shadow-sm ring-1 transition-all",
        "disabled:opacity-60",
        wishlisted
          ? "bg-rose-500 text-white ring-rose-600/20 hover:scale-110"
          : "bg-bg/80 backdrop-blur-sm text-text-tertiary hover:text-rose-500 hover:bg-bg ring-border hover:scale-105",
      )}
    >
      <Heart
        className={cn(
          "h-3.5 w-3.5 transition-transform",
          wishlisted && "fill-current",
        )}
      />
    </button>
  );
}
