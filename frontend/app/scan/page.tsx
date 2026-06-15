"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ArrowLeft, ScanLine } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";
import { CardScanner } from "@/components/scan/CardScanner";

export default function ScanPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login?redirect=/scan");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-16">
        <p className="text-text-tertiary text-sm">Checking session…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-6 sm:py-10">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Link
          href="/portfolio"
          className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <div className="text-right">
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-text-primary inline-flex items-center gap-2">
            <ScanLine className="h-5 w-5 text-accent-yellow" />
            Scan a card
          </h1>
          <p className="text-xs text-text-tertiary mt-0.5">
            Point at the card · Tap capture · Confirm
          </p>
        </div>
      </div>

      <CardScanner />

      <div className="mt-6 text-center text-[11px] text-text-tertiary font-mono">
        Powered by Claude Vision · Works best in good light, card centered.
      </div>
    </main>
  );
}
