export type User = {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  created_at: string;
  is_admin?: boolean;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type AccessTokenResponse = {
  access_token: string;
  token_type: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

const TOKEN_KEY = "pulllist_token";

export function saveToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
  // Server-readable hint cookie for track-visit attribution. The refresh
  // cookie (httpOnly, cross-origin) is the real credential — this one is
  // just so edge routes can tag visits to a user without a JS round-trip.
  // 60-day max-age matches the refresh window; contents are just the
  // current 15-min access JWT, so most of the time it holds an expired
  // token which the backend simply treats as anonymous.
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${60 * 60 * 24 * 60}; samesite=lax`;
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

// ────────── Refresh flow ──────────
//
// Access tokens are short (15 min). When a request comes back 401, we
// try the refresh endpoint once — the browser sends the httpOnly refresh
// cookie automatically because every auth-flow fetch uses credentials:
// 'include'. If refresh succeeds we retry the original call with the new
// access JWT; if it fails we clear local state and boot to /login.
//
// Single-flight: if ten API calls fire at once and all return 401, only
// the first call actually hits /auth/refresh; the other nine await the
// same promise so we don't rotate the token ten times in parallel.

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });
      if (!res.ok) return false;
      const body = (await res.json()) as AccessTokenResponse;
      if (!body?.access_token) return false;
      saveToken(body.access_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

function redirectToLogin() {
  if (typeof window === "undefined") return;
  // Don't loop the login page onto itself — some auth calls (like fetchMe
  // on first mount) will 401 there and we shouldn't clobber the form.
  const p = window.location.pathname;
  if (p.startsWith("/login") || p.startsWith("/signup")) return;
  window.location.href = "/login";
}

async function authFetch<T>(
  path: string,
  init: RequestInit = {},
  isRetry = false,
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
    // credentials:'include' so login/signup/google Set-Cookie lands in the
    // browser AND every subsequent call sends the refresh cookie back when
    // the endpoint scope matches (/api/v1/auth/*). CORS must be
    // allow_credentials on the backend for this to actually work.
    credentials: "include",
    cache: "no-store",
  });

  if (res.status === 401 && !isRetry && path !== "/auth/refresh") {
    const ok = await refreshAccessToken();
    if (ok) return authFetch<T>(path, init, true);
    clearToken();
    redirectToLogin();
    throw new Error("Session expired");
  }

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
  /** Honeypot — frontend renders a hidden field; humans leave it empty,
   *  bots auto-filling every input populate it. Always send what we have
   *  so the backend can decide. */
  website?: string,
): Promise<TokenResponse> {
  return authFetch<TokenResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, name, website }),
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

/** Revoke the current refresh token server-side and clear the cookie.
 *  Fire-and-forget on failures — a network hiccup shouldn't strand the
 *  user in a "half-logged-out" state locally. */
export async function serverLogout(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
  } catch {
    // ignore — local clearToken() still runs
  }
}

export async function logoutAllDevices(): Promise<void> {
  return authFetch<void>("/auth/logout-all", { method: "POST" });
}

export type SessionInfo = {
  id: string;
  device_label: string | null;
  created_at: string;
  last_used_at: string | null;
  expires_at: string;
  is_current: boolean;
};

export async function listSessions(): Promise<SessionInfo[]> {
  return authFetch<SessionInfo[]>("/auth/sessions");
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

/** Print variants matching TCGplayer's keys. 'normal' is the standard
 *  print, the others are reverse-holo / 1st-edition / holo / vintage
 *  patterns. Each variant has its own market price. */
export type CardVariant =
  | "normal"
  | "holofoil"
  | "reverseHolofoil"
  | "1stEdition"
  | "1stEditionHolofoil"
  | "unlimited"
  | "unlimitedHolofoil";

export type AcquisitionType =
  | "pull"
  | "trade"
  | "purchase"
  | "gift"
  | "other";

export type CollectionItemDetail = {
  id: number;
  card_id: string;
  qty: number;
  variant: CardVariant;
  condition: string;
  is_graded: boolean;
  grade: string | null;
  acquired_at: string | null;
  notes: string | null;
  purchase_price_usd: number | null;
  acquisition_type: AcquisitionType | null;
  created_at: string;
  card_name: string;
  card_number: string | null;
  image_small: string | null;
  rarity: string | null;
  market_price_usd: number | null;
  set_id: string;
  set_name: string;
};

export type CollectionItemCreatePayload = {
  card_id: string;
  qty?: number;
  variant?: CardVariant;
  condition?: "NM" | "LP" | "MP" | "HP" | "DMG";
  is_graded?: boolean;
  grade?: string | null;
  acquired_at?: string | null;
  notes?: string | null;
  purchase_price_usd?: number | null;
  acquisition_type?: AcquisitionType | null;
};

export async function createCollectionItem(
  payload: CollectionItemCreatePayload,
): Promise<CollectionItemDetail> {
  return authFetch<CollectionItemDetail>("/collection/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type CollectionItemUpdatePayload = Partial<
  Omit<CollectionItemCreatePayload, "card_id">
>;

export async function updateCollectionItem(
  itemId: number,
  payload: CollectionItemUpdatePayload,
): Promise<CollectionItemDetail> {
  return authFetch<CollectionItemDetail>(`/collection/items/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteCollectionItem(itemId: number): Promise<void> {
  await authFetch<void>(`/collection/items/${itemId}`, { method: "DELETE" });
}

// ────────── Card data-quality reports ──────────

export type CardReportCategory =
  | "wrong_price"
  | "wrong_image"
  | "wrong_name"
  | "other";

export type CardReportStatus = "open" | "resolved" | "wontfix";

export type CardReportRow = {
  id: number;
  card_id: string;
  card_name: string | null;
  card_number: string | null;
  card_image_small: string | null;
  set_id: string | null;
  set_name: string | null;
  category: CardReportCategory;
  comment: string | null;
  status: CardReportStatus;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
  reporter: { id: string; email: string; name: string | null } | null;
  resolver: { id: string; email: string; name: string | null } | null;
};

/** Public — anonymous OK (token is forwarded if present so logged-in
 *  reports get attributed to the user). */
export async function submitCardReport(
  cardId: string,
  payload: { category: CardReportCategory; comment?: string | null },
): Promise<{ id: number; status: string }> {
  return authFetch(`/cards/${cardId}/reports`, {
    method: "POST",
    body: JSON.stringify({
      category: payload.category,
      comment: payload.comment ?? null,
    }),
  });
}

export type SetReportCategory =
  | "missing_cards"
  | "wrong_images"
  | "wrong_metadata"
  | "other";

/** Public — anonymous OK. Mirrors submitCardReport but scoped to a
 * whole set (for gaps that don't fit a single card row, like
 * "cards are missing" or "logo is wrong"). */
export async function submitSetReport(
  setId: string,
  payload: { category: SetReportCategory; comment?: string | null },
): Promise<{ id: number; status: string }> {
  return authFetch(`/sets/${setId}/reports`, {
    method: "POST",
    body: JSON.stringify({
      category: payload.category,
      comment: payload.comment ?? null,
    }),
  });
}

export async function listCardReports(opts: {
  status?: CardReportStatus | "all";
  page?: number;
  pageSize?: number;
} = {}): Promise<{
  items: CardReportRow[];
  total: number;
  page: number;
  page_size: number;
}> {
  const qs = new URLSearchParams();
  if (opts.status) qs.set("status", opts.status);
  if (opts.page) qs.set("page", String(opts.page));
  if (opts.pageSize) qs.set("page_size", String(opts.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return authFetch(`/admin/card-reports${suffix}`);
}

export async function updateCardReport(
  reportId: number,
  payload: { status: CardReportStatus; resolution_note?: string | null },
): Promise<CardReportRow> {
  return authFetch(`/admin/card-reports/${reportId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export type SetReportStatus = "open" | "resolved" | "wontfix";

export type SetReportRow = {
  id: number;
  set_id: string;
  set_name: string | null;
  set_logo_url: string | null;
  category: SetReportCategory;
  comment: string | null;
  status: SetReportStatus;
  created_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
  reporter: { id: string; email: string; name: string | null } | null;
  resolver: { id: string; email: string; name: string | null } | null;
};

export async function listSetReports(opts: {
  status?: SetReportStatus | "all";
  page?: number;
  pageSize?: number;
} = {}): Promise<{
  items: SetReportRow[];
  total: number;
  page: number;
  page_size: number;
}> {
  const qs = new URLSearchParams();
  if (opts.status) qs.set("status", opts.status);
  if (opts.page) qs.set("page", String(opts.page));
  if (opts.pageSize) qs.set("page_size", String(opts.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return authFetch(`/admin/set-reports${suffix}`);
}

export async function updateSetReport(
  reportId: number,
  payload: { status: SetReportStatus; resolution_note?: string | null },
): Promise<SetReportRow> {
  return authFetch(`/admin/set-reports/${reportId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ────────── Visit logs / traffic admin ──────────

export type VisitsSummary = {
  views: { today: number; yesterday: number; week: number };
  uniques: { today: number; yesterday: number; week: number };
  countries_today: { country: string; count: number }[];
  daily_7d: { date: string; views: number; uniques: number }[];
};

export type VisitsByUserItem = {
  user_id: string;
  email: string | null;
  name: string | null;
  is_admin: boolean;
  views: number;
  last_seen: string | null;
  last_country: string | null;
};

export async function getVisitsSummary(): Promise<VisitsSummary> {
  return authFetch<VisitsSummary>("/admin/visits/summary");
}

export async function getVisitsByUser(
  days = 1,
): Promise<{ days: number; items: VisitsByUserItem[] }> {
  return authFetch(`/admin/visits/by-user?days=${days}`);
}

// ─── Extended visit tracking (2026-07) ─────────────────────────────

export type VisitScope = "all" | "anon" | "user";

export type VisitRecentItem = {
  id: number;
  created_at: string;
  path: string;
  referrer: string | null;
  country: string | null;
  region: string | null;
  city: string | null;
  device: string | null;
  session_id: string;
  is_anonymous: boolean;
  user: { id: string; email: string; name: string | null } | null;
};

export type TopPathItem = { path: string; views: number; uniques: number };
export type TopReferrerItem = { domain: string; views: number; uniques: number };
export type AnonSessionItem = {
  session_id: string;
  views: number;
  first_seen: string | null;
  last_seen: string | null;
  entry_path?: string;
  entry_referrer?: string;
  country?: string | null;
  city?: string | null;
  device?: string | null;
};

export async function getVisitsRecent(opts: {
  limit?: number;
  scope?: VisitScope;
} = {}): Promise<{ items: VisitRecentItem[]; limit: number; scope: VisitScope }> {
  const qs = new URLSearchParams();
  if (opts.limit) qs.set("limit", String(opts.limit));
  if (opts.scope) qs.set("scope", opts.scope);
  const suffix = qs.toString() ? `?${qs}` : "";
  return authFetch(`/admin/visits/recent${suffix}`);
}

export async function getVisitsTopPaths(
  days = 7,
  limit = 20,
): Promise<{ days: number; items: TopPathItem[] }> {
  return authFetch(`/admin/visits/top-paths?days=${days}&limit=${limit}`);
}

export async function getVisitsTopReferrers(
  days = 7,
  limit = 20,
): Promise<{ days: number; items: TopReferrerItem[] }> {
  return authFetch(`/admin/visits/top-referrers?days=${days}&limit=${limit}`);
}

export async function getVisitsAnonSessions(
  days = 7,
  limit = 50,
): Promise<{ days: number; items: AnonSessionItem[] }> {
  return authFetch(`/admin/visits/anon-sessions?days=${days}&limit=${limit}`);
}

// ────────── Single-card price refresh ──────────

export type CardRefreshResult = {
  card_id: string;
  market_price_usd: number | null;
  tcg_market: number | null;
  ebay_median: number | null;
  cached: boolean;
};

export async function refreshCardPrice(
  cardId: string,
): Promise<CardRefreshResult> {
  return authFetch<CardRefreshResult>(
    `/cards/${encodeURIComponent(cardId)}/refresh-price`,
    { method: "POST" },
  );
}

export async function toggleOwned(
  cardId: string,
  variant: CardVariant = "normal",
): Promise<{ owned: boolean; variant: CardVariant }> {
  return authFetch<{ owned: boolean; variant: CardVariant }>(
    `/collection/cards/${cardId}/toggle?variant=${variant}`,
    { method: "POST" },
  );
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

export async function bulkDeleteCollectionItems(
  ids: number[],
): Promise<void> {
  if (ids.length === 0) return;
  await authFetch<void>(`/collection/items/bulk-delete`, {
    method: "POST",
    body: JSON.stringify({ ids }),
    headers: { "Content-Type": "application/json" },
  });
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
  variant: CardVariant;
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
  variant: CardVariant = "normal",
): Promise<{ wishlisted: boolean; variant: CardVariant }> {
  return authFetch<{ wishlisted: boolean; variant: CardVariant }>(
    `/wishlist/cards/${cardId}/toggle?variant=${variant}`,
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
