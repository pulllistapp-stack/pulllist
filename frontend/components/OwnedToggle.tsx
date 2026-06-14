"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "./AuthProvider";
import { useCollection } from "./CollectionProvider";

type Props = {
  cardId: string;
  size?: "sm" | "md";
  variant?: "default" | "hero";
};

export function OwnedToggle({ cardId, size = "md", variant = "default" }: Props) {
  const { user } = useAuth();
  const { has, toggle } = useCollection();
  const [pending, setPending] = useState(false);

  // hero = single-layer full-width pill (used on card detail Cheapest hero).
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
    setPending(true);
    try {
      await toggle(cardId);
    } finally {
      setPending(false);
    }
  };

  // Hero variant: solid green when not owned (call-to-action), solid amber when owned (already in collection)
  const heroOwned =
    "bg-accent-yellow text-gray-900 hover:brightness-105 shadow-md shadow-accent-yellow/30";
  const heroNotOwned =
    "bg-accent-green text-white hover:brightness-105 shadow-md shadow-accent-green/30";

  // Default variant kept as-is
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
  );
}
