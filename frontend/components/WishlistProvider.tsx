"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { useAuth } from "./AuthProvider";
import { invalidateApiCache } from "@/lib/api";
import {
  wishlistIds as fetchWishlistIds,
  toggleWishlist,
  type CardVariant,
} from "@/lib/auth";

/**
 * Mirror of CollectionProvider for wishlist state. Same shape so the heart
 * toggle component can read it the same way the owned-check works.
 */

type WishlistContextValue = {
  wishlistedSet: Set<string>;
  loading: boolean;
  /** True if user wishlists any variant of this card. */
  has: (cardId: string) => boolean;
  /** Toggle a specific variant. Default 'normal'. */
  toggle: (cardId: string, variant?: CardVariant) => Promise<boolean>;
  refresh: () => Promise<void>;
};

const WishlistContext = createContext<WishlistContextValue | null>(null);

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [wishlistedSet, setWishlistedSet] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setWishlistedSet(new Set());
      return;
    }
    setLoading(true);
    try {
      const ids = await fetchWishlistIds();
      setWishlistedSet(new Set(ids));
    } catch {
      setWishlistedSet(new Set());
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const has = useCallback(
    (cardId: string) => wishlistedSet.has(cardId),
    [wishlistedSet],
  );

  const toggle = useCallback(
    async (
      cardId: string,
      variant: CardVariant = "normal",
    ): Promise<boolean> => {
      if (!user) return false;
      const result = await toggleWishlist(cardId, variant);
      setWishlistedSet((prev) => {
        const next = new Set(prev);
        if (result.wishlisted) next.add(cardId);
        else next.delete(cardId);
        return next;
      });
      if (!result.wishlisted) void refresh();
      invalidateApiCache("/wishlist");
      return result.wishlisted;
    },
    [user, refresh],
  );

  return (
    <WishlistContext.Provider
      value={{ wishlistedSet, loading, has, toggle, refresh }}
    >
      {children}
    </WishlistContext.Provider>
  );
}

export function useWishlist() {
  const ctx = useContext(WishlistContext);
  if (!ctx)
    throw new Error("useWishlist must be used within WishlistProvider");
  return ctx;
}
