export type SetWithCardCount = {
  id: string;
  name: string;
  series: string | null;
  printed_total: number | null;
  total: number | null;
  ptcgo_code: string | null;
  release_date: string | null;
  symbol_url: string | null;
  logo_url: string | null;
  card_count: number;
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
  tcgplayer_prices: Record<string, {
    low?: number | null;
    mid?: number | null;
    high?: number | null;
    market?: number | null;
    directLow?: number | null;
  }> | null;
  cardmarket_url: string | null;
  cardmarket_prices: Record<string, number | null> | null;
  market_price_usd: number | null;
  set_id: string;
  set_name: string | null;
  set_printed_total: number | null;
  set_ptcgo_code: string | null;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

export type CardList = {
  items: Card[];
  total: number;
  page: number;
  page_size: number;
};

export async function listSets(): Promise<SetWithCardCount[]> {
  return apiFetch<SetWithCardCount[]>("/sets");
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

export async function getFilterOptions(): Promise<FilterOptions> {
  return apiFetch<FilterOptions>("/cards/filters/options");
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

export async function browseCards(
  params: BrowseParams,
  token?: string,
): Promise<CardList> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    qs.set(k, String(v));
  }
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}/cards/browse?${qs.toString()}`, {
    cache: "no-store",
    headers,
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<CardList>;
}
