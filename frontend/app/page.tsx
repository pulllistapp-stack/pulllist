import Link from "next/link";

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function fetchHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return { status: "down" };
    return res.json();
  } catch {
    return { status: "down" };
  }
}

export default async function HomePage() {
  const health = await fetchHealth();
  const online = health.status === "ok";

  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <section className="mb-16">
        <h1 className="text-5xl font-bold tracking-tight leading-tight mb-4">
          Find Pokémon TCG in stock
          <br />
          near you, in real time.
        </h1>
        <p className="text-text-secondary max-w-2xl mb-8 text-lg">
          Catalog every set. Track every restock. Across Target, Walmart, Best
          Buy, GameStop, Costco, Pokémon Center — all on one map.
        </p>

        <div className="flex items-center gap-3 text-sm font-mono">
          <span
            className={`inline-flex h-2 w-2 rounded-full ${
              online ? "bg-accent-green pulse-dot text-accent-green" : "bg-accent-red"
            }`}
          />
          <span className="text-text-secondary">
            API {online ? "online" : "offline"}
          </span>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card
          title="Card catalog"
          body="Every Pokémon TCG card ever printed, seeded from pokemontcg.io."
          href="/sets"
          status="ready"
        />
        <Card
          title="Stock tracker"
          body="Live in-stock pings from major US retailers. Map view, distance, alerts."
          href="/map"
          status="coming"
        />
        <Card
          title="Collection"
          body="Track what you own. See your set completion %. Share with friends."
          href="/me/collection"
          status="ready"
        />
      </section>
    </main>
  );
}

function Card({
  title,
  body,
  href,
  status,
}: {
  title: string;
  body: string;
  href: string;
  status: "ready" | "coming";
}) {
  return (
    <Link
      href={href}
      className="block rounded-card bg-bg-surface border border-border p-6 hover:border-accent-yellow/40 transition-colors"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span
          className={`text-xs font-mono px-2 py-1 rounded-chip ${
            status === "ready"
              ? "bg-accent-green/10 text-accent-green"
              : "bg-text-tertiary/10 text-text-tertiary"
          }`}
        >
          {status === "ready" ? "READY" : "SOON"}
        </span>
      </div>
      <p className="text-sm text-text-secondary">{body}</p>
    </Link>
  );
}
