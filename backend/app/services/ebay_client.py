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

# Conservative default exclude list — only the clearly misleading patterns.
# Excluded EVERY broad term (etb, ultra-pro, pick, choose, lot, binder, etc.)
# because they also kill legitimate listings.
_DEFAULT_EXCLUDE_TERMS = (
    "code", "codes",        # TCGO online code-only listings
    "sleeves", "sleeve",    # empty sleeve packs
    "playmat",              # accessory only
    "empty",                # empty pack / box listings
    "proxy",                # counterfeit reproductions
    "fake", "replica",
    "custom",               # custom-painted / non-original
)


# Stricter list for single-card lookups (where bulk/lot/box listings would
# inflate or muddy the per-card median). Use via `exclude_terms=EXCLUDE_FOR_SINGLES`.
EXCLUDE_FOR_SINGLES = _DEFAULT_EXCLUDE_TERMS + (
    "lot", "bulk", "binder",
    "pickyourcard",         # multi-card "pick your card" listings
)


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
) -> str:
    """Compose the positive-term query for a single Pokémon card.

    Example: pokemon Charizard 4/102 Base Set
    Falls back gracefully when total/set is unknown.
    """
    parts: list[str] = ["pokemon", card_name.strip()]
    if card_number:
        num = card_number.strip()
        if printed_total and "/" not in num:
            num = f"{num}/{printed_total}"
        parts.append(num)
    if set_name:
        parts.append(set_name.strip())
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
        category_id: str | None = POKEMON_CATEGORIES["tcg_root"],
        max_results: int = 50,
        fixed_price_only: bool = True,
        new_only: bool = False,
        exclude_terms: list[str] | None = None,
        min_price_usd: float | None = None,
        max_price_usd: float | None = None,
    ) -> dict[str, Any] | None:
        """Fetch fixed-price listings and compute low / median / high USD.

        Defaults are tuned for Pokémon card lookups:
          - Restricts to Pokémon TCG category (`183454`)
          - Strips out code-card / sleeve / "pick your card" junk via negative terms
          - Fixed-price only (auctions skew the signal)

        Set `category_id=None` to search everywhere; pass `exclude_terms=[]`
        to disable the noise filter.

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

        # No explicit sort = eBay's relevance/bestMatch which represents the
        # typical market better than "price" (= cheapest first = junk-skewed).
        result = await self.browse_search(
            cleaned_query,
            limit=max_results,
            filters=filters or None,
            category_id=category_id,
        )

        items = result.get("itemSummaries") or []
        prices: list[float] = []
        for it in items:
            try:
                p = it.get("price") or {}
                v = float(p["value"])
                currency = p.get("currency", "USD")
                if currency == "USD" and v > 0:
                    prices.append(v)
            except (KeyError, TypeError, ValueError):
                continue

        if not prices:
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
            "total_listings": result.get("total", n),
            "cleaned_query": cleaned_query,
        }
