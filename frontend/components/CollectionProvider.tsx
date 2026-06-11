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
import { ownedIds as fetchOwnedIds, toggleOwned } from "@/lib/auth";

type CollectionContextValue = {
  ownedSet: Set<string>;
  loading: boolean;
  has: (cardId: string) => boolean;
  toggle: (cardId: string) => Promise<boolean>;
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
    async (cardId: string): Promise<boolean> => {
      if (!user) return false;
      const result = await toggleOwned(cardId);
      setOwnedSet((prev) => {
        const next = new Set(prev);
        if (result.owned) next.add(cardId);
        else next.delete(cardId);
        return next;
      });
      return result.owned;
    },
    [user],
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
