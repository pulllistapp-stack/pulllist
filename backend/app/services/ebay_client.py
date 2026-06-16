"""eBay Browse API client with cached OAuth client_credentials token.

We use the Application token (no eBay user login) since PullList only reads
public marketplace data. Token is cached for its full lifetime (~2 hours);
the next call after expiry auto-refreshes.

Docs:
  https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("ebay")


# Default scope for application-level Browse API access
_BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"

# eBay US category IDs — used to filter Pokémon-only results.
# These are public; you can verify in eBay's category browser.
POKEMON_CATEGORIES = {
    "tcg_root": "183454",              # Pokémon Trading Card Game (broadest)
    "singles": "183454",               # Pokémon Individual Cards (= same as root in some flows)
    "sealed_boosters": "183452",       # Pokémon Sealed Booster Packs
    "sealed_decks": "183455",          # Pokémon Sealed Decks
    "sealed_boxes": "183456",          # Pokémon Sealed Booster Boxes
}

# eBay Browse API doesn't reliably honor `-term` negative search syntax — for
# some specific queries it returns 0 results because it tries to match the
# literal "-term" string. We keep the q-string clean and post-filter results
# on the Python side instead.
_DEFAULT_EXCLUDE_TERMS = ()


# Title substrings used by `price_summary` to drop junk listings AFTER fetching.
# Reliable because we control the filter in code.
_TITLE_NOISE_DEFAULT = (
    # Online codes / accessories
    "code card", "code cards", "online code", "tcgo code",
    "sleeves", "sleeve",
    "playmat",
    "empty pack", "empty box",
    "proxy",
    "fake", "replica",
    "custom",
    # Graded slabs trade for 3-10x the raw card price — drop them so a single
    # PSA 10 listing doesn't dominate when there are no raw listings.
    "psa 10", "psa 9", "psa 8", "psa 7",
    "bgs 10", "bgs 9.5", "bgs 9", "bgs 8",
    "cgc 10", "cgc 9.5", "cgc 9", "cgc 8",
    "graded",
    # Sealed product — not a single-card price signal.
    "booster box", "booster pack", "elite trainer box", "etb",
    " sealed",  # leading space avoids matching "Resealed" / "concealed"
    # Multi-card listings
    "lot of", "bulk lot",
    "pick your card", "you choose", "you pick",
)

# Minimum eBay listings required before we trust the median. With fewer than
# this many results, a single outlier (graded slab, sealed booster) can
# dominate the snapshot. Without this guard, me2-125 (Mega Charizard X ex)
# matched exactly one $2,799 PSA listing and recorded that as the price even
# though TCGplayer market was $831.
_MIN_LISTINGS_FOR_PRICE = 3

_TITLE_NOISE_FOR_SINGLES = _TITLE_NOISE_DEFAULT + ("binder",)

# For chase rarities, sellers commonly include a disambiguator in titles.
# Appending these to the q-string sharply tightens results — a "Mega
# Charizard X ex" search returns 4+ different cards in the same set, but
# adding "SIR" narrows to the Special Illustration Rare specifically.
# Only used for high-variance rarities where mismatches actually happen.
_RARITY_QUERY_HINTS = {
    "Special Illustration Rare": "SIR",
    "Illustration Rare": "IR",
    "Hyper Rare": "Hyper Rare",
    "Rare Rainbow": "Rainbow Rare",
    "Mega Hyper Rare": "Mega Hyper Rare",
}

# Price-sanity bounds for listings vs the card's TCGplayer reference price.
# eBay raw cards can run 30-90% of TCGplayer, sometimes 100-200%. Anything
# outside (0.30, 5.0) × TCG market is almost certainly a different card,
# a sealed product, or a typo. me2-125 SIR was returning $75 listings at a
# $808 reference — that's 9%, clearly wrong-card noise.
_PRICE_FLOOR_RATIO = 0.30
_PRICE_CEILING_RATIO = 5.0
_PRICE_FLOOR_ABS = 0.50  # never reject prices above 50¢ as "too low"
_PRICE_CEILING_ABS = 20.0  # never reject prices below $20 as "too high"

# Kept for backwards-compat / callers that explicitly request stricter q-string excludes
EXCLUDE_FOR_SINGLES = _DEFAULT_EXCLUDE_TERMS


def build_query(positive_terms: str, *, exclude: list[str] | None = None) -> str:
    """Append `-word` negatives so eBay filters out junk listings."""
    excludes = list(_DEFAULT_EXCLUDE_TERMS if exclude is None else exclude)
    neg = " ".join(f"-{w}" for w in excludes if w)
    return f"{positive_terms} {neg}".strip()


def build_card_query(
    *,
    card_name: str,
    card_number: str | None = None,
    printed_total: int | None = None,
    set_name: str | None = None,
    rarity: str | None = None,
) -> str:
    """Compose the positive-term query for a single Pokémon card.

    Example: pokemon Charizard 4/102 Base Set
             pokemon Mega Charizard X ex 125/94 Phantasmal Flames SIR
    Falls back gracefully when total/set is unknown.

    Adds a rarity disambiguator for chase rarities (SIR, IR, Hyper, etc.) so
    a search like "Mega Charizard X ex" doesn't also match the cheap Double
    Rare variant in the same set.
    """
    parts: list[str] = ["pokemon", card_name.strip()]
    if card_number:
        num = card_number.strip()
        if printed_total and "/" not in num:
            num = f"{num}/{printed_total}"
        parts.append(num)
    if set_name:
        parts.append(set_name.strip())
    if rarity and rarity in _RARITY_QUERY_HINTS:
        parts.append(_RARITY_QUERY_HINTS[rarity])
    # collapse multiple spaces
    return " ".join(p for p in parts if p)


class EbayClientError(RuntimeError):
    pass


class EbayClient:
    """Async context-managed Browse API client.

    Usage:
        async with EbayClient() as ebay:
            data = await ebay.browse_search("pokemon charizard")
            summary = await ebay.price_summary("pokemon charizard psa 10")
    """

    def __init__(self, *, marketplace_id: str | None = None) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._http: httpx.AsyncClient | None = None
        self._marketplace_id = marketplace_id or settings.ebay_marketplace_id

    async def __aenter__(self) -> EbayClient:
        self._http = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------ auth

    async def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token

        app_id = settings.ebay_active_app_id
        cert_id = settings.ebay_active_cert_id
        if not app_id or not cert_id:
            raise EbayClientError(
                f"eBay {settings.ebay_env} credentials missing. "
                "Set EBAY_APP_ID + EBAY_CERT_ID (or EBAY_SANDBOX_APP_ID + "
                "EBAY_SANDBOX_CERT_ID) in backend/.env"
            )

        cred = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
        url = f"{settings.ebay_base_url}/identity/v1/oauth2/token"
        data = {"grant_type": "client_credentials", "scope": _BROWSE_SCOPE}
        headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        assert self._http is not None, "Use EbayClient as async context manager"
        r = await self._http.post(url, data=data, headers=headers)
        if r.status_code != 200:
            raise EbayClientError(
                f"Token request failed {r.status_code}: {r.text[:300]}"
            )
        body = r.json()
        self._token = body["access_token"]
        expires_in = int(body.get("expires_in", 7200))
        # 60-second safety buffer to avoid edge-of-expiry races
        self._token_expires_at = now + expires_in - 60
        log.info(
            f"eBay {settings.ebay_env} token acquired (valid {expires_in}s)"
        )
        return self._token

    # ------------------------------------------------------------------ Browse

    async def browse_search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        filters: dict[str, str] | None = None,
        category_id: str | None = None,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """Search active listings on eBay.

        `filters` example: {"buyingOptions": "FIXED_PRICE", "conditions": "NEW"}
        eBay encodes them as `key:{value}` joined by commas.

        Returns the raw response — typically:
          { itemSummaries: [...], total: N, href: "...", next: "..." }
        """
        token = await self._get_token()
        url = f"{settings.ebay_base_url}/buy/browse/v1/item_summary/search"

        params: dict[str, str] = {
            "q": query,
            "limit": str(min(max(limit, 1), 200)),
            "offset": str(max(offset, 0)),
        }
        if category_id:
            params["category_ids"] = category_id
        if sort:
            params["sort"] = sort

        if filters:
            parts = [f"{k}:{{{v}}}" for k, v in filters.items()]
            params["filter"] = ",".join(parts)

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self._marketplace_id,
            "Accept": "application/json",
        }

        assert self._http is not None
        r = await self._http.get(url, params=params, headers=headers)
        if r.status_code != 200:
            raise EbayClientError(
                f"Browse search failed {r.status_code} for q={query!r}: "
                f"{r.text[:500]}"
            )
        return r.json()

    async def price_summary(
        self,
        query: str,
        *,
        category_id: str | None = None,
        max_results: int = 50,
        fixed_price_only: bool = True,
        new_only: bool = False,
        exclude_terms: list[str] | None = None,
        min_price_usd: float | None = None,
        max_price_usd: float | None = None,
        reference_price_usd: float | None = None,
    ) -> dict[str, Any] | None:
        """Fetch fixed-price listings and compute low / median / high USD.

        Defaults are tuned for Pokémon card lookups:
          - Restricts to Pokémon TCG category (`183454`)
          - Strips out code-card / sleeve / "pick your card" junk via negative terms
          - Fixed-price only (auctions skew the signal)

        Set `category_id=None` to search everywhere; pass `exclude_terms=[]`
        to disable the noise filter.

        `reference_price_usd` (typically Card.market_price_usd from TCGplayer)
        enables price-sanity filtering — listings outside (0.30, 5.0) × ref
        are dropped as obvious wrong-card noise. me2-125 SIR ($808 TCG ref)
        was previously matching $75 listings (DR variants) and recording a
        useless median; with this filter on, only listings in the $242–$4040
        band count.

        Returns None if no usable price data.
        """
        filters: dict[str, str] = {}
        if fixed_price_only:
            filters["buyingOptions"] = "FIXED_PRICE"
        if new_only:
            filters["conditions"] = "NEW"
        if min_price_usd is not None or max_price_usd is not None:
            lo = "" if min_price_usd is None else f"{min_price_usd:.2f}"
            hi = "" if max_price_usd is None else f"{max_price_usd:.2f}"
            # eBay price filter form: price:[lo..hi],priceCurrency:USD
            filters["price"] = f"[{lo}..{hi}]"
            filters["priceCurrency"] = "USD"

        cleaned_query = build_query(query, exclude=exclude_terms)
        total_listings_hint = 0

        # Price-sanity bounds computed once from the reference.
        sanity_floor: float | None = None
        sanity_ceiling: float | None = None
        if reference_price_usd is not None and reference_price_usd > 0:
            sanity_floor = max(reference_price_usd * _PRICE_FLOOR_RATIO, _PRICE_FLOOR_ABS)
            sanity_ceiling = max(
                reference_price_usd * _PRICE_CEILING_RATIO, _PRICE_CEILING_ABS
            )

        async def _fetch_prices(active_filters: dict[str, str]) -> list[float]:
            nonlocal total_listings_hint
            res = await self.browse_search(
                cleaned_query,
                limit=max_results,
                filters=active_filters or None,
                category_id=category_id,
            )
            total_listings_hint = int(res.get("total") or 0) or total_listings_hint
            out: list[float] = []
            for it in res.get("itemSummaries") or []:
                # Python-side title filter — eBay's q-string `-term` syntax is unreliable
                title = (it.get("title") or "").lower()
                if any(n in title for n in _TITLE_NOISE_DEFAULT):
                    continue
                try:
                    p = it.get("price") or {}
                    v = float(p["value"])
                    currency = p.get("currency", "USD")
                    if currency != "USD" or v <= 0:
                        continue
                    # Price-sanity vs TCGplayer reference, when available.
                    if sanity_floor is not None and v < sanity_floor:
                        continue
                    if sanity_ceiling is not None and v > sanity_ceiling:
                        continue
                    out.append(v)
                except (KeyError, TypeError, ValueError):
                    continue
            return out

        # First pass — respect caller's settings (fixed-price by default).
        prices = await _fetch_prices(filters)

        # Fallback for hot/new cards that are mostly auctions (e.g. Cinccino ex SIR):
        # if we got nothing under FIXED_PRICE, retry including auctions so the
        # snapshot captures *some* signal instead of being NULL.
        if not prices and fixed_price_only:
            relaxed = {k: v for k, v in filters.items() if k != "buyingOptions"}
            prices = await _fetch_prices(relaxed)

        # Require a minimum sample size — a single listing isn't a median.
        # Better to record nothing than to capture a PSA-slab outlier as the
        # market price for a raw card.
        if not prices or len(prices) < _MIN_LISTINGS_FOR_PRICE:
            return None

        prices.sort()
        n = len(prices)
        median = (
            prices[n // 2]
            if n % 2
            else (prices[n // 2 - 1] + prices[n // 2]) / 2
        )
        return {
            "low": prices[0],
            "median": median,
            "high": prices[-1],
            "count_sampled": n,
            "total_listings": total_listings_hint or n,
            "cleaned_query": cleaned_query,
        }
