export type User = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const TOKEN_KEY = "pulllist_token";

export function saveToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${60 * 60 * 24 * 14}; samesite=lax`;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
}

async function authFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = `API ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function signup(
  email: string,
  password: string,
  name?: string,
): Promise<TokenResponse> {
  return authFetch<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
}

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  return authFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function loginWithGoogle(
  credential: string,
): Promise<TokenResponse> {
  return authFetch<TokenResponse>("/auth/google", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });
}

export async function fetchMe(): Promise<User> {
  return authFetch<User>("/auth/me");
}

export async function deleteMe(): Promise<void> {
  return authFetch<void>("/auth/me", { method: "DELETE" });
}

export type CollectionSummary = {
  total_entries: number;
  unique_cards: number;
  total_qty: number;
  sets_touched: number;
  estimated_value_usd: number;
};

export type SetCompletion = {
  set_id: string;
  set_name: string;
  total_cards: number;
  owned_unique: number;
  owned_total_qty: number;
  completion_pct: number;
  estimated_value_usd: number;
};

export type CollectionItemDetail = {
  id: number;
  card_id: string;
  qty: number;
  condition: string;
  is_graded: boolean;
  grade: string | null;
  acquired_at: string | null;
  notes: string | null;
  created_at: string;
  card_name: string;
  card_number: string | null;
  image_small: string | null;
  rarity: string | null;
  market_price_usd: number | null;
  set_id: string;
  set_name: string;
};

export async function toggleOwned(cardId: string): Promise<{ owned: boolean }> {
  return authFetch<{ owned: boolean }>(`/collection/cards/${cardId}/toggle`, {
    method: "POST",
  });
}

export async function ownedIds(setId?: string): Promise<string[]> {
  const qs = setId ? `?set_id=${encodeURIComponent(setId)}` : "";
  return authFetch<string[]>(`/collection/owned-ids${qs}`);
}

export async function setCompletion(setId: string): Promise<SetCompletion> {
  return authFetch<SetCompletion>(`/collection/sets/${setId}/completion`);
}

export async function collectionSummary(): Promise<CollectionSummary> {
  return authFetch<CollectionSummary>(`/collection/summary`);
}

export async function listMyItems(
  setId?: string,
): Promise<CollectionItemDetail[]> {
  const qs = setId ? `?set_id=${encodeURIComponent(setId)}` : "";
  return authFetch<CollectionItemDetail[]>(`/collection/items${qs}`);
}

// ────────── Wishlist ──────────

export type WishlistSummary = {
  total: number;
  estimated_value_usd: number;
  at_target_count: number;
};

export type WishlistItemDetail = {
  id: number;
  card_id: string;
  priority: number;
  max_price_usd: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  card_name: string;
  card_number: string | null;
  image_small: string | null;
  rarity: string | null;
  market_price_usd: number | null;
  set_id: string;
  set_name: string;
  target_met: boolean;
};

export async function toggleWishlist(
  cardId: string,
): Promise<{ wishlisted: boolean }> {
  return authFetch<{ wishlisted: boolean }>(
    `/wishlist/cards/${cardId}/toggle`,
    { method: "POST" },
  );
}

export async function wishlistIds(): Promise<string[]> {
  return authFetch<string[]>("/wishlist/ids");
}

export async function wishlistSummary(): Promise<WishlistSummary> {
  return authFetch<WishlistSummary>("/wishlist/summary");
}

export async function listMyWishlist(opts: {
  setId?: string;
  onlyTargetMet?: boolean;
} = {}): Promise<WishlistItemDetail[]> {
  const qs = new URLSearchParams();
  if (opts.setId) qs.set("set_id", opts.setId);
  if (opts.onlyTargetMet) qs.set("only_target_met", "true");
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return authFetch<WishlistItemDetail[]>(`/wishlist/items${suffix}`);
}

export async function updateWishlistItem(
  itemId: number,
  payload: { priority?: number; max_price_usd?: number | null; notes?: string | null },
): Promise<void> {
  return authFetch(`/wishlist/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteWishlistItem(itemId: number): Promise<void> {
  return authFetch(`/wishlist/items/${itemId}`, { method: "DELETE" });
}

// ────────── Portfolio history (Growth chart) ──────────

export type PortfolioPoint = {
  date: string;
  value: number;
  unique_cards: number;
  total_qty: number;
  sets_touched: number;
};

export type PortfolioHistory = {
  period_days: number;
  points: PortfolioPoint[];
  first_value: number;
  latest_value: number;
  delta_usd: number;
  delta_pct: number;
  count: number;
};

export async function getPortfolioHistory(
  periodDays = 30,
): Promise<PortfolioHistory> {
  return authFetch<PortfolioHistory>(
    `/collection/portfolio/history?period_days=${periodDays}`,
  );
}

// ────────── Card scanning (Claude Vision) ──────────

export type ScanIdentification = {
  card_name: string | null;
  card_number: string | null;
  set_name: string | null;
  confidence: "high" | "medium" | "low";
  notes: string | null;
};

export type ScanCandidate = {
  id: string;
  name: string;
  number: string | null;
  set_id: string;
  set_name: string;
  rarity: string | null;
  image_small: string | null;
  market_price_usd: number | null;
};

export type ScanResponse = {
  identification: ScanIdentification;
  candidates: ScanCandidate[];
  matched_card_id: string | null;
};

export async function scanCard(
  imageData: string,
  mediaType = "image/jpeg",
): Promise<ScanResponse> {
  return authFetch<ScanResponse>("/cards/scan", {
    method: "POST",
    body: JSON.stringify({ image_data: imageData, media_type: mediaType }),
  });
}

// ────────── Portfolio sharing ──────────

export type SharingSettings = {
  is_public: boolean;
  share_token: string | null;
  share_url: string | null;
  bio: string | null;
  show_value: boolean;
  show_growth: boolean;
  show_wishlist: boolean;
  show_all_cards: boolean;
};

export type SharingUpdate = Partial<{
  is_public: boolean;
  bio: string | null;
  show_value: boolean;
  show_growth: boolean;
  show_wishlist: boolean;
  show_all_cards: boolean;
}>;

export async function getMySharing(): Promise<SharingSettings> {
  return authFetch<SharingSettings>("/me/sharing");
}

export async function updateMySharing(
  payload: SharingUpdate,
): Promise<SharingSettings> {
  return authFetch<SharingSettings>("/me/sharing", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function rotateShareToken(): Promise<SharingSettings> {
  return authFetch<SharingSettings>("/me/sharing/rotate", {
    method: "POST",
  });
}
