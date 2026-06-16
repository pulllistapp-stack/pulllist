"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ArrowLeft, Camera, ScanLine, Smartphone } from "lucide-react";

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
          <p className="hidden sm:block text-xs text-text-tertiary mt-0.5">
            Point at the card · Tap capture · Confirm
          </p>
        </div>
      </div>

      {/* Mobile: full camera scanner */}
      <div className="md:hidden">
        <CardScanner />
        <div className="mt-6 text-center text-[11px] text-text-tertiary font-mono">
          Powered by Claude Vision
        </div>
      </div>

      {/* Desktop: mobile-only message + QR */}
      <div className="hidden md:block">
        <DesktopFallback />
      </div>
    </main>
  );
}

function DesktopFallback() {
  // Use a public QR generator API — avoids adding a JS library for one icon.
  const scanUrl = "https://pulllist.org/scan";
  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&margin=8&data=${encodeURIComponent(scanUrl)}`;

  return (
    <div className="rounded-3xl border border-border bg-bg-surface p-8 sm:p-12 text-center">
      <div className="mx-auto mb-5 inline-flex h-16 w-16 items-center justify-center rounded-full bg-accent-yellow/15 text-accent-yellow">
        <Smartphone className="h-8 w-8" />
      </div>
      <h2 className="text-2xl font-extrabold text-text-primary">
        Card scanning is mobile-only
      </h2>
      <p className="mt-2 text-sm text-text-secondary max-w-md mx-auto">
        Hold your phone&apos;s camera up to a card — that&apos;s the whole flow.
        Desktop doesn&apos;t have the rear camera or the framing UX that makes
        this work, so we kept the scanner phone-first.
      </p>

      <div className="mt-8 flex flex-col items-center gap-3">
        <div className="rounded-2xl bg-white p-3 shadow-md">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={qrSrc}
            alt="Scan QR to open PullList on phone"
            width={220}
            height={220}
            className="block"
          />
        </div>
        <p className="text-xs text-text-tertiary font-mono">
          Point your phone&apos;s camera at this QR → open the link
        </p>
        <p className="text-[11px] text-text-tertiary">
          Or visit{" "}
          <span className="font-mono text-text-secondary">
            pulllist.org/scan
          </span>{" "}
          on your phone directly.
        </p>
      </div>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 text-left max-w-md mx-auto">
        <Tip num="1" text="Install PullList to your home screen first (Share → Add to Home Screen)" />
        <Tip num="2" text="Tap the floating yellow scan button bottom-right" />
        <Tip num="3" text="Camera opens → align the card → tap Capture" />
      </div>
    </div>
  );
}

function Tip({ num, text }: { num: string; text: string }) {
  return (
    <div className="rounded-xl border border-border bg-bg p-3">
      <p className="text-[10px] font-mono uppercase tracking-wider text-accent-yellow">
        Step {num}
      </p>
      <p className="mt-1 text-xs text-text-secondary leading-snug">{text}</p>
    </div>
  );
}
