"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "./AuthProvider";
import { useCollection } from "./CollectionProvider";
import { CardAddModal } from "./card/CardAddModal";
import { invalidateApiCache } from "@/lib/api";
import type { CardVariant } from "@/lib/auth";

type CardForModal = {
  id: string;
  name: string;
  number?: string | null;
  image_small?: string | null;
  tcgplayer_prices?: unknown;
};

type Props = {
  cardId: string;
  size?: "sm" | "md";
  variant?: "default" | "hero";
  /** Print variant the toggle adds/removes. Default 'normal'. */
  printVariant?: CardVariant;
  /** Card payload used to populate the "+ I have this" modal. When
   *  provided, clicking the not-owned button opens the modal instead of
   *  doing a 1-click add. Without it, the legacy 1-click toggle runs. */
  card?: CardForModal;
};

export function OwnedToggle({
  cardId,
  size = "md",
  variant = "default",
  printVariant = "normal",
  card,
}: Props) {
  const { user } = useAuth();
  const { has, toggle, refresh } = useCollection();
  const [pending, setPending] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  const isHero = variant === "hero";
  const sizeCls = isHero
    ? "text-sm px-5 py-3"
    : size === "sm"
      ? "text-xs px-2 py-1"
      : "text-sm px-3 py-1.5";
  const widthCls = isHero ? "w-full sm:w-auto sm:flex-1 justify-center" : "";
  const radiusCls = isHero ? "rounded-full" : "rounded-btn";

  if (!user) {
    return (
      <Link
        href="/login"
        className={`inline-flex items-center gap-1.5 ${radiusCls} ${widthCls} border border-border text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary ${sizeCls}`}
      >
        Log in to track
      </Link>
    );
  }

  const owned = has(cardId);

  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (pending) return;

    if (!owned && card) {
      setModalOpen(true);
      return;
    }

    setPending(true);
    try {
      await toggle(cardId, printVariant);
    } finally {
      setPending(false);
    }
  };

  const onAdded = async () => {
    invalidateApiCache("/cards/browse");
    await refresh();
  };

  const heroOwned =
    "bg-accent-yellow text-gray-900 hover:brightness-105 shadow-md shadow-accent-yellow/30";
  const heroNotOwned =
    "bg-accent-green text-white hover:brightness-105 shadow-md shadow-accent-green/30";

  const defaultOwned =
    "bg-accent-green/15 text-accent-green border border-accent-green/30 hover:bg-accent-green/20";
  const defaultNotOwned =
    "border border-border text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary";

  const stateCls = isHero
    ? owned
      ? heroOwned
      : heroNotOwned
    : owned
      ? defaultOwned
      : defaultNotOwned;

  return (
    <>
      <button
        onClick={onClick}
        disabled={pending}
        className={`inline-flex items-center gap-1.5 font-bold transition-colors ${sizeCls} ${radiusCls} ${widthCls} ${stateCls} disabled:opacity-50`}
        aria-pressed={owned}
      >
        {owned ? (
          <>
            <span aria-hidden>✓</span>
            <span>{isHero ? "In your collection" : "Owned"}</span>
          </>
        ) : (
          <>
            <span aria-hidden>+</span>
            <span>I have this</span>
          </>
        )}
      </button>

      {modalOpen && card && (
        <CardAddModal
          card={card}
          initialVariant={printVariant}
          onClose={() => setModalOpen(false)}
          onAdded={onAdded}
        />
      )}
    </>
  );
}
