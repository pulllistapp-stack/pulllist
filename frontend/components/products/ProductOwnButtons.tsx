"use client";

/**
 * Two toggle buttons on the product detail page — mark this sealed
 * product as owned, and add / remove from wishlist.
 *
 * Server-rendered detail page mounts this as a client island. It
 * bootstraps state by hitting /sealed/collection/product/{id} +
 * /sealed/wishlist/product/{id} in parallel and shows a soft
 * "Sign in to track" prompt when the visitor isn't logged in.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bookmark, Check, Heart, HeartOff, Plus } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import {
  deleteSealedOwnership,
  getSealedOwnership,
  getSealedState,
  toggleSealedWishlist,
  upsertSealedOwnership,
} from "@/lib/api";

type Props = {
  productId: string;
  productName: string;
};

export function ProductOwnButtons({ productId, productName }: Props) {
  const { user, loading: authLoading } = useAuth();
  const [owned, setOwned] = useState(false);
  const [wishlisted, setWishlisted] = useState(false);
  const [busy, setBusy] = useState<"own" | "wish" | null>(null);
  const [initialLoaded, setInitialLoaded] = useState(false);

  // Bootstrap: on mount, fetch current ownership + wishlist state.
  // Use the bulk /sealed/state endpoint so a single request answers
  // both questions — cheaper than two round-trips even for one product.
  useEffect(() => {
    if (!user) {
      setInitialLoaded(true);
      return;
    }
    let cancelled = false;
    getSealedState([productId])
      .then((state) => {
        if (cancelled) return;
        setOwned(state.owned.includes(productId));
        setWishlisted(state.wishlisted.includes(productId));
      })
      .catch(() => {
        /* leave defaults; user can still click */
      })
      .finally(() => {
        if (!cancelled) setInitialLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [productId, user]);

  const handleOwnToggle = async () => {
    if (!user || busy) return;
    setBusy("own");
    try {
      if (owned) {
        await deleteSealedOwnership(productId);
        setOwned(false);
      } else {
        await upsertSealedOwnership(productId, { qty: 1 });
        setOwned(true);
      }
    } catch {
      /* swallow — a failed toggle just leaves the button clickable */
    } finally {
      setBusy(null);
    }
  };

  const handleWishlistToggle = async () => {
    if (!user || busy) return;
    setBusy("wish");
    try {
      const res = await toggleSealedWishlist(productId);
      setWishlisted(res.wishlisted);
    } catch {
      /* swallow */
    } finally {
      setBusy(null);
    }
  };

  if (authLoading) {
    return (
      <div className="mt-4 h-10 w-64 animate-pulse rounded-full bg-bg-surface/60" />
    );
  }

  if (!user) {
    return (
      <div className="mt-4 rounded-full border border-dashed border-border/60 bg-bg-surface/30 px-4 py-2 text-xs text-text-tertiary">
        <Link
          href={`/login?next=${encodeURIComponent(`/products/${productId}`)}`}
          className="text-accent-yellow hover:underline"
        >
          Sign in
        </Link>{" "}
        to track this sealed product in your collection or wishlist.
      </div>
    );
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={handleOwnToggle}
        disabled={busy === "own" || !initialLoaded}
        aria-pressed={owned}
        aria-label={owned ? `Un-own ${productName}` : `Mark ${productName} as owned`}
        className={
          "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 " +
          (owned
            ? "border-accent-green/50 bg-accent-green/10 text-accent-green hover:bg-accent-green/15"
            : "border-border bg-bg-surface text-text-primary hover:border-accent-green/40")
        }
      >
        {owned ? (
          <>
            <Check className="h-4 w-4" />
            In your collection
          </>
        ) : (
          <>
            <Plus className="h-4 w-4" />
            Mark as owned
          </>
        )}
      </button>

      <button
        type="button"
        onClick={handleWishlistToggle}
        disabled={busy === "wish" || !initialLoaded}
        aria-pressed={wishlisted}
        aria-label={
          wishlisted
            ? `Remove ${productName} from wishlist`
            : `Add ${productName} to wishlist`
        }
        className={
          "inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 " +
          (wishlisted
            ? "border-accent-red/50 bg-accent-red/10 text-accent-red hover:bg-accent-red/15"
            : "border-border bg-bg-surface text-text-primary hover:border-accent-red/40")
        }
      >
        {wishlisted ? (
          <>
            <Heart className="h-4 w-4" fill="currentColor" />
            On wishlist
          </>
        ) : (
          <>
            <Bookmark className="h-4 w-4" />
            Add to wishlist
          </>
        )}
      </button>
    </div>
  );
}
