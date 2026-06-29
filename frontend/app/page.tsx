import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  History,
  Library,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { FinalCTA, HeroCTA } from "@/components/HomeCTAs";

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function safeFetch<T = unknown>(
  url: string,
  timeoutMs = 8000,
): Promise<T | null> {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

type Mover = {
  card_id: string;
  name?: string | null;
  set_name?: string | null;
  delta_pct: number;
  current_price?: number | null;
  image_url?: string | null;
};

type SetSummary = {
  id: string;
  name: string;
  series?: string | null;
  card_count?: number | null;
  total_value_usd?: number | null;
  total_value_mid_usd?: number | null;
  total_value_low_usd?: number | null;
  total_value_high_usd?: number | null;
  released_at?: string | null;
  logo_url?: string | null;
};

export default async function HomePage() {
  // Render free-tier cold start can take up to ~50s. Keep the hero static so the
  // first paint never blocks on the API — let the data sections degrade gracefully.
  const [trending, sets, health] = await Promise.all([
    safeFetch<{ movers: Mover[] }>(
      `${API_BASE}/cards/trending?period_days=7&direction=up&limit=4`,
    ),
    safeFetch<SetSummary[]>(`${API_BASE}/sets?limit=20`),
    safeFetch<{ status?: string }>(`${API_BASE}/health`, 30_000),
  ]);

  const online = health?.status === "ok";
  const movers = trending?.movers ?? [];
  const newestSets = Array.isArray(sets) ? sets.slice(0, 3) : [];

  return (
    <main className="relative overflow-hidden">
      {/* ────────── HERO ────────── */}
      <section className="relative mx-auto max-w-7xl px-6 pt-12 pb-20 sm:pt-20 sm:pb-28">
        {/* Atmospheric glows */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 -left-24 h-[28rem] w-[28rem] rounded-full bg-accent-yellow/10 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-teal-400/10 blur-3xl"
        />

        <div className="relative grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-12 lg:gap-16 items-center">
          {/* LEFT — copy + CTA */}
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-yellow/15 text-accent-yellow border border-accent-yellow/30 px-3 py-1 text-xs font-mono uppercase tracking-wider mb-6">
              <Sparkles className="h-3 w-3 fill-amber-400" aria-hidden />
              EN · JP · KR catalogs
            </span>

            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.03] text-text-primary">
              Track every pull.
              <br />
              <span className="bg-gradient-to-r from-accent-yellow via-amber-400 to-teal-400 bg-clip-text text-transparent">
                From booster to vault.
              </span>
            </h1>

            <p className="mt-6 text-lg text-text-secondary max-w-xl leading-relaxed">
              The Pokémon TCG collection tracker for serious pullers. Live eBay
              and TCGplayer prices, daily history, English / Japanese / Korean
              catalogs — search any card in any language.
            </p>

            <HeroCTA />

            {/* Stats strip */}
            <dl className="mt-10 flex flex-wrap items-end gap-x-10 gap-y-4">
              <Stat value="31,000+" label="cards indexed" />
              <Stat value="340+" label="sets covered" />
              <Stat value="Daily" label="price snapshots" />
            </dl>
          </div>

          {/* RIGHT — mascot composition */}
          <div className="relative flex items-center justify-center">
            <HeroArt />
          </div>
        </div>
      </section>

      {/* ────────── TRENDING STRIP ────────── */}
      {movers.length > 0 && (
        <section className="border-y border-border bg-bg-surface/40 backdrop-blur-sm">
          <div className="mx-auto max-w-7xl px-6 py-12">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-accent-green" />
                  Trending this week
                </h2>
                <p className="mt-1 text-sm text-text-secondary">
                  Biggest 7-day gainers across the catalog.
                </p>
              </div>
              <Link
                href="/trending"
                className="hidden sm:inline-flex items-center gap-1 text-sm text-teal-500 font-semibold hover:text-teal-400"
              >
                See all <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </Link>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {movers.slice(0, 4).map((m) => (
                <MoverCard key={m.card_id} mover={m} />
              ))}
            </div>

            <div className="mt-5 sm:hidden">
              <Link
                href="/trending"
                className="text-sm text-teal-500 font-semibold"
              >
                See all gainers →
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* ────────── FEATURED SETS ────────── */}
      {newestSets.length > 0 && (
        <section className="mx-auto max-w-7xl px-6 py-16">
          <div className="flex items-center justify-between mb-7">
            <div>
              <h2 className="text-2xl font-bold">Latest sets</h2>
              <p className="mt-1 text-sm text-text-secondary">
                Fresh drops — track set value and chase completion.
              </p>
            </div>
            <Link
              href="/sets"
              className="hidden sm:inline-flex items-center gap-1 text-sm text-teal-500 font-semibold hover:text-teal-400"
            >
              All sets <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
            {newestSets.map((s) => (
              <SetCard key={s.id} set={s} />
            ))}
          </div>
        </section>
      )}

      {/* ────────── FEATURE PILLARS ────────── */}
      <section className="mx-auto max-w-7xl px-6 pb-16">
        <h2 className="text-2xl font-bold mb-7">Built for collectors</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <FeatureCard
            iconBg="bg-accent-yellow/15"
            icon={<Library className="h-6 w-6 text-accent-yellow" />}
            title="Every card indexed"
            body="31,000+ cards across 340+ sets in English, Japanese, and Korean — Base Set through the latest Mega Evolution drops."
            href="/cards"
          />
          <FeatureCard
            iconBg="bg-accent-green/15"
            icon={<TrendingUp className="h-6 w-6 text-accent-green" />}
            title="Live market prices"
            body="Daily eBay and TCGplayer snapshots. Median pricing tracked across every variant."
            href="/trending"
          />
          <FeatureCard
            iconBg="bg-teal-400/15"
            icon={<History className="h-6 w-6 text-teal-400" />}
            title="Price history"
            body="See the full price arc on any card — 7d, 30d, 90d, 1y. Catch gainers before they spike."
            href="/trending"
          />
        </div>
      </section>

      {/* ────────── FINAL CTA ────────── */}
      <section className="mx-auto max-w-7xl px-6 pb-20">
        <div className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-accent-yellow/10 via-amber-200/5 to-teal-400/10 dark:from-accent-yellow/10 dark:via-amber-500/5 dark:to-teal-500/10 px-8 py-12 sm:px-12 sm:py-16 text-center">
          <Sparkles
            aria-hidden
            className="absolute top-6 left-10 h-6 w-6 text-amber-400 fill-amber-400 opacity-60 [animation:pl-float-c_4s_ease-in-out_infinite]"
          />
          <Sparkles
            aria-hidden
            className="absolute bottom-8 right-12 h-5 w-5 text-teal-400 fill-teal-400 opacity-60 [animation:pl-float-a_5s_ease-in-out_infinite]"
          />
          <FinalCTA />
        </div>

        {/* System status — tiny, bottom-right */}
        <div className="mt-6 flex items-center justify-end gap-2 text-[11px] font-mono text-text-tertiary">
          <span
            className={`inline-flex h-1.5 w-1.5 rounded-full ${
              online ? "bg-accent-green pulse-dot text-accent-green" : "bg-accent-red"
            }`}
          />
          API {online ? "online" : "offline"}
        </div>
      </section>
    </main>
  );
}

// ────────── components ──────────

function HeroArt() {
  return (
    <div className="relative h-[22rem] w-[22rem] sm:h-[26rem] sm:w-[26rem] flex items-center justify-center">
      {/* Outer dashed ring — empty, slow spin */}
      <div
        aria-hidden
        className="absolute inset-0 rounded-full border-2 border-dashed border-teal-400/60 dark:border-teal-300/40 [animation:pl-slow-spin_32s_linear_infinite]"
      />

      {/* Inner mascot disc — gently floats. Uses the smooth duo illustration
          (logo asset) here rather than the pixel idle APNG; pixel art lives
          in the loading mascots only — at hero scale it fights the rest of
          the modern UI. */}
      <div className="relative h-64 w-64 sm:h-72 sm:w-72 rounded-full bg-white flex items-center justify-center p-6 shadow-[0_22px_50px_-14px_rgba(0,0,0,0.32)] dark:shadow-[0_25px_60px_-12px_rgba(20,184,166,0.5)] [animation:pl-float_5s_ease-in-out_infinite]">
        <Image
          src="/pullist-mascot-logo.png"
          alt=""
          width={240}
          height={240}
          className="object-contain"
          unoptimized
          priority
        />
      </div>

      {/* Floating tiny cards — three of them, each on its own clock */}
      <div
        aria-hidden
        className="absolute -top-2 -right-2 sm:-top-4 sm:right-2 [animation:pl-float-a_5.5s_ease-in-out_infinite]"
      >
        <div className="h-20 w-14 rounded-lg bg-gradient-to-br from-rose-300 via-amber-300 to-yellow-300 shadow-xl rotate-12" />
      </div>
      <div
        aria-hidden
        className="absolute -bottom-3 -left-2 sm:-bottom-6 sm:left-4 [animation:pl-float-b_6.5s_ease-in-out_infinite]"
      >
        <div className="h-20 w-14 rounded-lg bg-gradient-to-br from-teal-300 via-blue-400 to-indigo-400 shadow-xl -rotate-12" />
      </div>
      <div
        aria-hidden
        className="absolute top-12 -left-6 sm:top-8 sm:-left-8 [animation:pl-float-c_5s_ease-in-out_infinite]"
      >
        <div className="h-16 w-12 rounded-lg bg-gradient-to-br from-fuchsia-300 to-rose-400 shadow-xl -rotate-6" />
      </div>

      {/* Sparkles */}
      <Sparkles
        aria-hidden
        className="absolute top-2 right-0 sm:top-6 sm:-right-6 h-6 w-6 text-amber-400 fill-amber-400 [animation:pl-float-a_4s_ease-in-out_infinite]"
      />
      <Sparkles
        aria-hidden
        className="absolute bottom-6 right-12 h-4 w-4 text-teal-400 fill-teal-400 [animation:pl-float-c_5s_ease-in-out_infinite]"
      />
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col">
      <dt className="order-2 text-[11px] font-mono uppercase tracking-wider text-text-tertiary mt-1">
        {label}
      </dt>
      <dd className="order-1 text-2xl sm:text-3xl font-extrabold text-text-primary">
        {value}
      </dd>
    </div>
  );
}

function MoverCard({ mover }: { mover: Mover }) {
  const up = (mover.delta_pct ?? 0) >= 0;
  const deltaColor = up ? "text-accent-green" : "text-accent-red";
  return (
    <Link
      href={`/cards/${mover.card_id}`}
      className="group relative block rounded-2xl border border-border bg-bg p-4 hover:border-accent-yellow/40 hover:-translate-y-1 transition-all duration-200"
    >
      <p
        className="text-sm font-semibold text-text-primary truncate"
        title={mover.name ?? mover.card_id}
      >
        {mover.name ?? mover.card_id}
      </p>
      {mover.set_name && (
        <p className="text-xs text-text-tertiary truncate mt-0.5">
          {mover.set_name}
        </p>
      )}
      <div className="mt-3 flex items-baseline justify-between">
        <span className={`text-lg font-bold ${deltaColor}`}>
          {up ? "+" : ""}
          {(mover.delta_pct ?? 0).toFixed(1)}%
        </span>
        {mover.current_price != null && (
          <span className="text-xs font-mono text-text-secondary">
            ${mover.current_price.toFixed(2)}
          </span>
        )}
      </div>
    </Link>
  );
}

function fmtCompactPrice(v: number | null | undefined): string | null {
  if (v == null || v <= 0) return null;
  if (v >= 10000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 1000) return `$${(v / 1000).toFixed(2)}k`;
  if (v >= 10) return `$${v.toFixed(0)}`;
  if (v >= 1) return `$${v.toFixed(1)}`;
  return `$${v.toFixed(2)}`;
}

function SetCard({ set }: { set: SetSummary }) {
  // Mid sum is the headline; falls back to market sum when the set's
  // cards haven't been backfilled yet. high captures graded-slab
  // outliers and overstates what a raw collector would actually pay.
  const valueLabel = fmtCompactPrice(set.total_value_mid_usd ?? set.total_value_usd);

  return (
    <Link
      href={`/sets/${set.id}`}
      className="group block rounded-2xl border border-border bg-bg-surface p-6 hover:border-accent-yellow/40 hover:-translate-y-1 transition-all duration-200"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-[11px] font-mono uppercase tracking-wider text-text-tertiary">
          {set.series ?? "Pokémon TCG"}
        </p>
        {valueLabel && (
          <span className="text-[11px] font-mono text-accent-yellow font-bold">
            {valueLabel}
          </span>
        )}
      </div>
      <h3 className="text-lg font-bold text-text-primary group-hover:text-accent-yellow transition-colors">
        {set.name}
      </h3>
      <p className="mt-2 text-sm text-text-secondary">
        {set.card_count ?? "?"} cards
      </p>
    </Link>
  );
}

function FeatureCard({
  icon,
  iconBg,
  title,
  body,
  href,
}: {
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  body: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group block rounded-2xl border border-border bg-bg-surface p-6 hover:border-accent-yellow/40 hover:-translate-y-1 transition-all duration-200"
    >
      <div
        className={`inline-flex h-12 w-12 items-center justify-center rounded-xl ${iconBg} mb-4`}
      >
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2 group-hover:text-accent-yellow transition-colors">
        {title}
      </h3>
      <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
    </Link>
  );
}
