export type SetType =
  | "MAIN"
  | "DECK"
  | "STUB"
  | "PROMO_LEGACY"
  | "PROMO_NEW";

export type SetSubtype = "STARTER" | "DECK" | "BOX" | "SPECIAL";

export type SetWithCardCount = {
  id: string;
  name: string;
  language: "en" | "ja" | "ko";
  name_ko: string | null;
  name_en: string | null;
  series: string | null;
  printed_total: number | null;
  total: number | null;
  ptcgo_code: string | null;
  release_date: string | null;
  symbol_url: string | null;
  logo_url: string | null;
  set_type: SetType | null;
  set_subtype: SetSubtype | null;
  card_count: number;
  total_value_usd: number | null;
  total_value_mid_usd: number | null;
  total_value_low_usd: number | null;
  total_value_high_usd: number | null;
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

export const API_BASE =
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

export type PopularPokemon = {
  name: string;
  count: number;
  image_small: string | null;
};

export async function getPopularPokemon(limit = 10): Promise<PopularPokemon[]> {
  return apiFetch<PopularPokemon[]>(`/cards/popular-pokemon?limit=${limit}`);
}

export type CardSearchSort =
  | "relevance"
  | "price_desc"
  | "price_asc"
  | "newest"
  | "oldest";

export async function searchCards(
  q: string,
  page = 1,
  pageSize = 50,
  sort: CardSearchSort = "relevance",
): Promise<CardList> {
  const sortQs = sort && sort !== "relevance" ? `&sort=${sort}` : "";
  return apiFetch<CardList>(
    `/cards/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}${sortQs}`,
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
  seller_feedback_score?: number | null;
  seller_trust_tier?: "new" | "low" | "poor" | "ok" | "trusted";
  /** Backend-flagged: low-trust seller asking <40% of market median.
   *  See backend/app/services/listing_match.py is_suspicious(). */
  suspicious?: boolean;
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

export type TrendingTier = "all" | "bulk" | "chase";
export type TrendingEra = "all" | "modern" | "classic";

export async function getTrending(opts: {
  periodDays?: number;
  source?: string;
  direction?: "up" | "down";
  limit?: number;
  minPriceUsd?: number;
  maxPriceUsd?: number;
  minAbsChangeUsd?: number;
  tier?: TrendingTier;
  era?: TrendingEra;
} = {}): Promise<TrendingResponse> {
  const qs = new URLSearchParams();
  if (opts.periodDays != null) qs.set("period_days", String(opts.periodDays));
  if (opts.source) qs.set("source", opts.source);
  if (opts.direction) qs.set("direction", opts.direction);
  if (opts.limit != null) qs.set("limit", String(opts.limit));
  if (opts.minPriceUsd != null) qs.set("min_price_usd", String(opts.minPriceUsd));
  if (opts.maxPriceUsd != null) qs.set("max_price_usd", String(opts.maxPriceUsd));
  if (opts.minAbsChangeUsd != null)
    qs.set("min_abs_change_usd", String(opts.minAbsChangeUsd));
  if (opts.tier && opts.tier !== "all") qs.set("tier", opts.tier);
  if (opts.era && opts.era !== "all") qs.set("era", opts.era);
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
  language?: string;
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

// ── Master Sets ────────────────────────────────────────────────────
// Set-completion tracker. Server-side row stores prefs only; progress
// numbers are recomputed on each read against the caller's collection.
// Types mirror backend/app/api/master_sets.py's Pydantic schemas.

export type BinderSize = "3x3" | "4x3" | "4x4";
export type MasterSetDisplayMode = "base" | "master";
export type MasterSetSortMode = "number" | "rarity";

export type MasterSet = {
  id: number;
  set_id: string;
  set_name: string;
  set_logo_url: string | null;
  set_release_date: string | null;
  binder_size: BinderSize;
  display_mode: MasterSetDisplayMode;
  sort_mode: MasterSetSortMode;
  total_base: number;
  owned_base: number;
  total_master: number;
  owned_master: number;
  cover_image_url: string | null;
  share_token: string | null;
  completed_at: string | null;
  just_completed: boolean;
  created_at: string;
  updated_at: string;
};

export type BinderSlot = {
  card_id: string;
  number: string | null;
  number_int: number | null;
  name: string;
  rarity: string | null;
  image_small: string | null;
  variant: string;
  owned: boolean;
};

export type BinderView = {
  master_set: MasterSet;
  slots: BinderSlot[];
};

async function authedFetch<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = "";
    try {
      const text = await res.text();
      detail = text ? ` — ${text.slice(0, 200)}` : "";
    } catch {
      /* ignore */
    }
    throw new Error(`API ${res.status}${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function listMasterSets(token: string): Promise<MasterSet[]> {
  return authedFetch<MasterSet[]>(`/master-sets`, token);
}

export function createMasterSet(
  payload: {
    set_id: string;
    binder_size?: BinderSize;
    display_mode?: MasterSetDisplayMode;
    sort_mode?: MasterSetSortMode;
  },
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets`, token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMasterSet(
  id: number,
  payload: {
    binder_size?: BinderSize;
    display_mode?: MasterSetDisplayMode;
    sort_mode?: MasterSetSortMode;
  },
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteMasterSet(id: number, token: string): Promise<void> {
  return authedFetch<void>(`/master-sets/${id}`, token, { method: "DELETE" });
}

export function getBinderView(
  id: number,
  opts: {
    mode?: MasterSetDisplayMode;
    sort?: MasterSetSortMode;
  },
  token: string,
): Promise<BinderView> {
  const qs = new URLSearchParams();
  if (opts.mode) qs.set("mode", opts.mode);
  if (opts.sort) qs.set("sort", opts.sort);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return authedFetch<BinderView>(`/master-sets/${id}${suffix}`, token);
}

export function setMasterSetCover(
  id: number,
  imageDataUrl: string,
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets/${id}/cover`, token, {
    method: "PUT",
    body: JSON.stringify({ image_data_url: imageDataUrl }),
  });
}

export function clearMasterSetCover(
  id: number,
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets/${id}/cover`, token, {
    method: "DELETE",
  });
}

export function enableMasterSetShare(
  id: number,
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets/${id}/share`, token, {
    method: "POST",
  });
}

export function revokeMasterSetShare(
  id: number,
  token: string,
): Promise<MasterSet> {
  return authedFetch<MasterSet>(`/master-sets/${id}/share`, token, {
    method: "DELETE",
  });
}

export function getPublicBinderView(publicToken: string): Promise<BinderView> {
  // Public endpoint — no auth token required.
  return fetch(`${API_BASE}/master-sets/public/${publicToken}`, {
    cache: "no-store",
  }).then(async (res) => {
    if (!res.ok) throw new Error(`API ${res.status}`);
    return (await res.json()) as BinderView;
  });
}

// ── Sealed products ────────────────────────────────────────────────

export type ProductType =
  | "booster_box"
  | "etb"
  | "booster_bundle"
  | "premium_collection"
  | "tin"
  | "blister"
  | "build_battle"
  | "sleeved_booster"
  | "other";

export type Product = {
  id: string;
  name: string;
  set_id: string | null;
  set_name: string | null;
  product_type: ProductType;
  packs_per_box: number | null;
  tcgplayer_product_id: number | null;
  market_price_usd: number | null;
  low_price_usd: number | null;
  high_price_usd: number | null;
  msrp_usd: number | null;
  image_url: string | null;
  tcgplayer_url: string | null;
};

export type ProductEV = {
  pack_ev_usd: number | null;
  box_ev_usd: number | null;
  packs_used: number | null;
  market_price_usd: number | null;
  premium_pct: number | null;
};

export type ProductDetail = Product & {
  ev: ProductEV | null;
  description: string | null;
};

export type ProductList = {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
};

export type ProductBrowseParams = {
  set_id?: string;
  product_type?: ProductType;
  sort?: "newest" | "price_desc" | "price_asc" | "name";
  page?: number;
  page_size?: number;
};

export function listProducts(params: ProductBrowseParams = {}): Promise<ProductList> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiFetch<ProductList>(`/products${suffix}`);
}

export function getProduct(id: string): Promise<ProductDetail> {
  return apiFetch<ProductDetail>(`/products/${id}`);
}

export function listProductsForSet(setId: string): Promise<Product[]> {
  return apiFetch<Product[]>(`/products/set/${setId}/list`);
}

export type ProductHistoryPoint = {
  date: string;
  market: number | null;
  low: number | null;
  mid: number | null;
  high: number | null;
};

export type ProductHistory = {
  product_id: string;
  product_name: string;
  days: number;
  points: ProductHistoryPoint[];
};

export function getProductHistory(
  id: string,
  days = 90,
): Promise<ProductHistory> {
  return apiFetch<ProductHistory>(`/products/${id}/history?days=${days}`);
}

export type ProductLiveListing = {
  title: string;
  price_usd: number;
  shipping_usd: number;
  total_usd: number;
  url: string | null;
  image_url: string | null;
  seller: string | null;
  condition: string | null;
  location: string | null;
};

export type ProductLiveListings = {
  listings: ProductLiveListing[];
  query: string;
  product_id?: string;
  error?: string;
};

export function getProductLiveListings(
  id: string,
  limit = 12,
): Promise<ProductLiveListings> {
  return apiFetch<ProductLiveListings>(
    `/products/${id}/live-listings?limit=${limit}`,
  );
}

// ── Series (roadmap §10.8 G) ────────────────────────────────────

export type SeriesSummary = {
  series: string;
  slug: string;
  set_count: number;
  card_count: number;
  product_count: number;
  latest_release: string | null;
};

export type SeriesSetPayload = {
  id: string;
  name: string;
  release_date: string | null;
  printed_total: number | null;
  total: number | null;
  logo_url: string | null;
  symbol_url: string | null;
  card_count: number;
};

export type SeriesProductPayload = {
  id: string;
  name: string;
  set_id: string | null;
  product_type: ProductType;
  market_price_usd: number | null;
  image_url: string | null;
  tcgplayer_url: string | null;
};

export type SeriesDetail = {
  series: string;
  slug: string;
  set_count: number;
  card_count: number;
  product_count: number;
  sets: SeriesSetPayload[];
  products: SeriesProductPayload[];
};

export function listSeries(): Promise<{ items: SeriesSummary[] }> {
  return apiFetch<{ items: SeriesSummary[] }>("/series");
}

export function getSeries(slug: string): Promise<SeriesDetail> {
  return apiFetch<SeriesDetail>(`/series/${slug}`);
}

// ── Sealed collection / wishlist (Products roadmap §10.8 B) ──────

export type SealedCollectionItem = {
  id: number;
  product_id: string;
  qty: number;
  purchase_price_usd: number | null;
  acquisition_type: string | null;
  acquired_at: string | null;
  notes: string | null;
};

export type SealedCollectionEntry = {
  item: SealedCollectionItem;
  product: {
    id: string;
    name: string;
    product_type: ProductType;
    set_id: string | null;
    market_price_usd: number | null;
    image_url: string | null;
    tcgplayer_url: string | null;
  };
};

export type SealedCollectionList = {
  items: SealedCollectionEntry[];
  total_owned: number;
  unique_products: number;
  estimated_value_usd: number;
};

export type SealedWishlistItem = {
  id: number;
  product_id: string;
  target_price_usd: number | null;
  notes: string | null;
};

export type SealedWishlistEntry = {
  item: SealedWishlistItem;
  product: SealedCollectionEntry["product"];
};

export type SealedWishlistList = {
  items: SealedWishlistEntry[];
  count: number;
};

export type SealedState = {
  owned: string[];
  wishlisted: string[];
};

export type SealedCollectionWrite = {
  qty?: number;
  purchase_price_usd?: number | null;
  acquisition_type?: string | null;
  acquired_at?: string | null;
  notes?: string | null;
};

async function authJson<T>(path: string, init?: RequestInit): Promise<T> {
  const { authFetch } = await import("./auth");
  return authFetch<T>(path, init);
}

export function listSealedCollection(): Promise<SealedCollectionList> {
  return authJson<SealedCollectionList>("/sealed/collection");
}

export function getSealedOwnership(productId: string) {
  return authJson<SealedCollectionItem | null>(
    `/sealed/collection/product/${productId}`,
  );
}

export function upsertSealedOwnership(
  productId: string,
  payload: SealedCollectionWrite,
): Promise<SealedCollectionItem> {
  return authJson<SealedCollectionItem>(
    `/sealed/collection/product/${productId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Content-Type": "application/json" },
    },
  );
}

export function deleteSealedOwnership(productId: string): Promise<{ ok: true }> {
  return authJson<{ ok: true }>(
    `/sealed/collection/product/${productId}`,
    { method: "DELETE" },
  );
}

export function listSealedWishlist(): Promise<SealedWishlistList> {
  return authJson<SealedWishlistList>("/sealed/wishlist");
}

export function toggleSealedWishlist(
  productId: string,
): Promise<{ wishlisted: boolean }> {
  return authJson<{ wishlisted: boolean }>(
    `/sealed/wishlist/product/${productId}/toggle`,
    { method: "POST" },
  );
}

export function getSealedState(
  productIds: string[],
): Promise<SealedState> {
  const qs = new URLSearchParams({ product_ids: productIds.join(",") });
  return authJson<SealedState>(`/sealed/state?${qs.toString()}`);
}

export function listMasterSetsForCard(
  cardId: string,
  token: string,
): Promise<MasterSet[]> {
  return authedFetch<MasterSet[]>(
    `/master-sets/for-card/${encodeURIComponent(cardId)}`,
    token,
  );
}

export function collectSpread(
  masterSetId: number,
  spreadIndex: number,
  mode: MasterSetDisplayMode | null,
  token: string,
): Promise<{ added: number }> {
  return authedFetch<{ added: number }>(
    `/master-sets/${masterSetId}/spread/${spreadIndex}/collect`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ mode }),
    },
  );
}
