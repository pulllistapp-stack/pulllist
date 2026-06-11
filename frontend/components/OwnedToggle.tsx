"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "./AuthProvider";
import { useCollection } from "./CollectionProvider";

type Props = {
  cardId: string;
  size?: "sm" | "md";
};

export function OwnedToggle({ cardId, size = "md" }: Props) {
  const { user } = useAuth();
  const { has, toggle } = useCollection();
  const [pending, setPending] = useState(false);

  const cls = size === "sm" ? "text-xs px-2 py-1" : "text-sm px-3 py-1.5";

  if (!user) {
    return (
      <Link
        href="/login"
        className={`inline-flex items-center gap-1.5 rounded-btn border border-border text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary ${cls}`}
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
    setPending(true);
    try {
      await toggle(cardId);
    } finally {
      setPending(false);
    }
  };

  return (
    <button
      onClick={onClick}
      disabled={pending}
      className={`inline-flex items-center gap-1.5 rounded-btn font-medium transition-colors ${cls} ${
        owned
          ? "bg-accent-green/15 text-accent-green border border-accent-green/30 hover:bg-accent-green/20"
          : "border border-border text-text-secondary hover:border-accent-yellow/40 hover:text-text-primary"
      } disabled:opacity-50`}
      aria-pressed={owned}
    >
      {owned ? (
        <>
          <span aria-hidden>✓</span>
          <span>Owned</span>
        </>
      ) : (
        <>
          <span aria-hidden>+</span>
          <span>I have this</span>
        </>
      )}
    </button>
  );
}
