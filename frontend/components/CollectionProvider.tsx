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
  ownedIds as fetchOwnedIds,
  toggleOwned,
  type CardVariant,
} from "@/lib/auth";

type CollectionContextValue = {
  ownedSet: Set<string>;
  loading: boolean;
  /** True if user owns ANY variant of this card. card-id grain — for
   *  detail-page variant-precise checks, call the API directly. */
  has: (cardId: string) => boolean;
  /** Toggle ownership of a specific variant. Default 'normal'. */
  toggle: (cardId: string, variant?: CardVariant) => Promise<boolean>;
  refresh: () => Promise<void>;
};

const CollectionContext = createContext<CollectionContextValue | null>(null);

export function CollectionProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [ownedSet, setOwnedSet] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setOwnedSet(new Set());
      return;
    }
    setLoading(true);
    try {
      const ids = await fetchOwnedIds();
      setOwnedSet(new Set(ids));
    } catch {
      setOwnedSet(new Set());
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const has = useCallback(
    (cardId: string) => ownedSet.has(cardId),
    [ownedSet],
  );

  const toggle = useCallback(
    async (
      cardId: string,
      variant: CardVariant = "normal",
    ): Promise<boolean> => {
      if (!user) return false;
      const result = await toggleOwned(cardId, variant);
      setOwnedSet((prev) => {
        const next = new Set(prev);
        if (result.owned) next.add(cardId);
        else {
          // Card-id grain — only remove the indicator if the user
          // truly owns no variants. We don't know without a refetch,
          // so optimistically remove and refresh once.
          next.delete(cardId);
        }
        return next;
      });
      if (!result.owned) {
        // Re-sync in case other variants remain owned.
        void refresh();
      }
      // Drop browse/owned caches so collection-filtered lists pick this up.
      invalidateApiCache("/cards/browse");
      return result.owned;
    },
    [user, refresh],
  );

  return (
    <CollectionContext.Provider
      value={{ ownedSet, loading, has, toggle, refresh }}
    >
      {children}
    </CollectionContext.Provider>
  );
}

export function useCollection() {
  const ctx = useContext(CollectionContext);
  if (!ctx)
    throw new Error("useCollection must be used within CollectionProvider");
  return ctx;
}
