export type SetWithCardCount = {
  id: string;
  name: string;
  name_ko: string | null;
  name_en: string | null;
  series: string | null;
  printed_total: number | null;
  total: number | null;
  ptcgo_code: string | null;
  release_date: string | null;
  symbol_url: string | null;
  logo_url: string | null;
  card_count: number;
  total_value_usd: number | null;
  owned_unique: number | null;
};

export type Card = {
  id: string;
  name: string;
  supertype: string | null;
  subtypes: string[] | null;
  types: string[] | null;
  hp: string | null;
  rarity: string | null;
  number: string | null;
  artist: string | null;
  flavor_text: string | null;
  national_pokedex_numbers: number[] | null;
  image_small: string | null;
  image_large: string | null;
  tcgplayer_url: string | null;
  tcgplayer_product_id: number | null;
  tcgplayer_prices: Record<string, {
    low?: number | null;
    mid?: number | null;
    high?: number | null;
    market?: number | null;
    directLow?: number | null;
  }> | null;
  market_price_usd: number | null;
  set_id: string;
  set_name: string | null;
  set_printed_total: number | null;
  set_ptcgo_code: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

/**
 * Tiny in-memory cache for GET responses. Keeps navigation between pages
 * snappy — clicking back to a set you just visited shows instantly while
 * we revalidate in the background. Mutations call `invalidateApiCache()`
 * to drop stale entries.
 */
type CacheEntry = { data: unknown; expires: number };
const cache = new Map<string, CacheEntry>();
const DEFAULT_TTL_MS = 5 * 60 * 1000; // 5 minutes

export function invalidateApiCache(prefix?: string) {
  if (!prefix) {
    cache.clear();
    return;
  }
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) cache.delete(key);
  }
}

async function apiFetch<T>(path: string, ttlMs = DEFAULT_TTL_MS): Promise<T> {
  // Server-side rendering: don't cache (separate process per request).
  if (typeof window === "undefined") {
    const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
    return res.json() as Promise<T>;
  }

  const now = Date.now();
  const cached = cache.get(path);
  if (cached && cached.expires > now) {
    return cached.data as T;
  }

  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  const data = (await res.json()) as T;
  cache.set(path, { data, expires: now + ttlMs });
  return data;
}

export type CardList = {
  items: Card[];
  total: number;
  page: number;
  page_size: number;
};

export type CatalogRegion = "en" | "ja" | "ko";

export async function listSets(opts: {
  token?: string;
  region?: CatalogRegion;
} = {}): Promise<SetWithCardCount[]> {
  const region = opts.region ?? "en";
  const qs = `?language=${region}`;
  if (!opts.token) {
    return apiFetch<SetWithCardCount[]>(`/sets${qs}`);
  }
  // With a token, include it so the backend can fill in `owned_unique`
  // per set for the requesting user. Bypass the in-memory cache because
  // the response is user-specific.
  const res = await fetch(`${API_BASE}/sets${qs}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${opts.token}` },
  });
  if (!res.ok) throw new Error(`API ${res.status}: /sets`);
  return res.json() as Promise<SetWithCardCount[]>;
}

export async function getSet(id: string) {
  return apiFetch<SetWithCardCount>(`/sets/${id}`);
}

export async function listCardsInSet(
  setId: string,
  page = 1,
  pageSize = 100,
): Promise<CardList> {
  return apiFetch<CardList>(
    `/sets/${setId}/cards?page=${page}&page_size=${pageSize}`,
  );
}

export async function getCard(cardId: string): Promise<Card> {
  return apiFetch<Card>(`/cards/${cardId}`);
}

export type Suggestion = {
  id: string;
  name: string;
  number: string | null;
  set_id: string;
  set_name: string | null;
  image_small: string | null;
  rarity: string | null;
  market_price_usd: number | null;
};

export async function suggestCards(q: string, limit = 8): Promise<Suggestion[]> {
  return apiFetch<Suggestion[]>(
    `/cards/suggest?q=${encodeURIComponent(q)}&limit=${limit}`,
  );
}

export async function searchCards(
  q: string,
  page = 1,
  pageSize = 50,
): Promise<CardList> {
  return apiFetch<CardList>(
    `/cards/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`,
  );
}

export async function getAlternates(cardId: string, limit = 12): Promise<Card[]> {
  return apiFetch<Card[]>(`/cards/${cardId}/alternates?limit=${limit}`);
}

export type CardNeighbor = {
  id: string;
  name: string;
  number: string | null;
  image_small: string | null;
};

export type CardNeighbors = {
  prev: CardNeighbor | null;
  next: CardNeighbor | null;
  position: number | null;
  total: number;
};

export async function getCardNeighbors(cardId: string): Promise<CardNeighbors> {
  return apiFetch<CardNeighbors>(`/cards/${cardId}/neighbors`);
}

export type CardHistoryPoint = {
  date: string;
  market: number | null;
  low: number | null;
  mid: number | null;
  high: number | null;
  sales: number | null;
};

export type CardHistory = {
  card_id: string;
  card_name: string;
  days: number;
  series_count: number;
  /** Key format: `<source>:<variant>` — e.g. `"ebay:active"`, `"tcgplayer:holofoil"`. */
  series: Record<string, CardHistoryPoint[]>;
};

export async function getCardHistory(
  cardId: string,
  opts: { source?: string; variant?: string; days?: number } = {},
): Promise<CardHistory> {
  const qs = new URLSearchParams();
  if (opts.source) qs.set("source", opts.source);
  if (opts.variant) qs.set("variant", opts.variant);
  if (opts.days != null) qs.set("days", String(opts.days));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<CardHistory>(`/cards/${cardId}/history${suffix}`);
}

export type LiveListing = {
  title: string;
  price_usd: number;
  shipping_usd: number;
  total_usd: number;
  condition: string;
  seller: string;
  seller_feedback_pct: number | string | null;
  url: string;
  image_url?: string | null;
  source: "eBay" | "TCGplayer";
};

export type LiveListingsResponse = {
  listings: LiveListing[];
  query: string;
  count?: number;
  error?: string;
};

export async function getLiveListings(
  cardId: string,
  limit = 10,
): Promise<LiveListingsResponse> {
  return apiFetch<LiveListingsResponse>(
    `/cards/${cardId}/live-listings?limit=${limit}`,
  );
}

// ────────── Public portfolio (sharing) ──────────

export type PublicCardEntry = {
  card_id: string;
  name: string;
  number: string | null;
  set_id: string;
  set_name: string;
  rarity: string | null;
  image_small: string | null;
  market_price_usd: number | null;
  qty: number;
};

export type PublicSetCompletion = {
  set_id: string;
  set_name: string;
  owned_unique: number;
  total_cards: number;
  completion_pct: number;
};

export type PublicGrowthPoint = {
  date: string;
  value: number;
};

export type PublicWishlistEntry = {
  card_id: string;
  name: string;
  set_name: string;
  image_small: string | null;
  market_price_usd: number | null;
  max_price_usd: number | null;
  priority: number;
};

export type PublicPortfolio = {
  display_name: string;
  bio: string | null;
  unique_cards: number;
  total_qty: number;
  sets_touched: number;
  estimated_value_usd: number | null;
  asset_mix: { label: string; value: number }[];
  top_cards: PublicCardEntry[];
  set_completion: PublicSetCompletion[];
  growth: PublicGrowthPoint[] | null;
  wishlist: PublicWishlistEntry[] | null;
  all_cards: PublicCardEntry[] | null;
};

export async function getPublicPortfolio(
  token: string,
): Promise<PublicPortfolio> {
  return apiFetch<PublicPortfolio>(`/p/${encodeURIComponent(token)}`);
}

/**
 * Downloads the caller's collection as a CSV file. The browser File API
 * doesn't let us attach Authorization headers to a plain <a download>,
 * so we fetch the blob ourselves, build an object URL, and trigger a
 * synthetic click. Caller must pass the JWT.
 */
export async function downloadCollectionCsv(token: string): Promise<void> {
  const res = await fetch(`${API_BASE}/collection/export.csv`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    // Surface the real status + body so the alert isn't a black box.
    let detail = "";
    try {
      const text = await res.text();
      detail = text ? ` — ${text.slice(0, 200)}` : "";
    } catch {
      // ignore body-read failures
    }
    throw new Error(`Export failed (HTTP ${res.status})${detail}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  // Match the server's Content-Disposition filename so older browsers
  // that ignore the header still get a reasonable default.
  const today = new Date().toISOString().slice(0, 10);
  a.download = `pulllist-collection-${today}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Defer revoke so Safari has time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export type TrendingMover = {
  card_id: string;
  latest_price: number;
  oldest_price: number;
  delta_pct: number;
  snapshots_count: number;
  name?: string;
  number?: string | null;
  set_id?: string;
  set_name?: string;
  image_small?: string | null;
  rarity?: string | null;
};

export type TrendingResponse = {
  period_days: number;
  source: string;
  direction: "up" | "down";
  movers: TrendingMover[];
  total_eligible: number;
};

export async function getTrending(opts: {
  periodDays?: number;
  source?: string;
  direction?: "up" | "down";
  limit?: number;
  minPriceUsd?: number;
  minAbsChangeUsd?: number;
} = {}): Promise<TrendingResponse> {
  const qs = new URLSearchParams();
  if (opts.periodDays != null) qs.set("period_days", String(opts.periodDays));
  if (opts.source) qs.set("source", opts.source);
  if (opts.direction) qs.set("direction", opts.direction);
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  if (opts.minPriceUsd != null) qs.set("min_price_usd", String(opts.minPriceUsd));
  if (opts.minAbsChangeUsd != null)
    qs.set("min_abs_change_usd", String(opts.minAbsChangeUsd));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<TrendingResponse>(`/cards/trending${suffix}`);
}

export type FilterOptions = {
  rarities: string[];
  supertypes: string[];
  types: string[];
  subtypes: string[];
  hp_max: number;
  price_max: number;
  sets: { id: string; name: string; series: string | null; release_date: string | null }[];
  artists: { name: string; count: number }[];
  conditions: string[];
  sort_options: string[];
};

export async function getFilterOptions(
  setId?: string,
): Promise<FilterOptions> {
  const qs = setId ? `?set_id=${encodeURIComponent(setId)}` : "";
  return apiFetch<FilterOptions>(`/cards/filters/options${qs}`);
}

export type BrowseParams = {
  q?: string;
  set_id?: string;
  rarity?: string;
  supertype?: string;
  type?: string;
  subtype?: string;
  hp_min?: number;
  hp_max?: number;
  price_min?: number;
  price_max?: number;
  artist?: string;
  owned?: "in" | "not_in";
  condition?: string;
  sort?: string;
  page?: number;
  page_size?: number;
};

const BROWSE_TTL_MS = 60 * 1000; // 1 minute — browse can change with collection toggles

export async function browseCards(
  params: BrowseParams,
  token?: string,
): Promise<CardList> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const cacheKey = `/cards/browse?${qs.toString()}${token ? `::auth=${token.slice(0, 12)}` : ""}`;

  // Server-side: skip cache
  if (typeof window !== "undefined") {
    const now = Date.now();
    const cached = cache.get(cacheKey);
    if (cached && cached.expires > now) {
      return cached.data as CardList;
    }
  }

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/cards/browse?${qs.toString()}`, {
    cache: "no-store",
    headers,
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const data = (await res.json()) as CardList;

  if (typeof window !== "undefined") {
    cache.set(cacheKey, { data, expires: Date.now() + BROWSE_TTL_MS });
  }
  return data;
}
