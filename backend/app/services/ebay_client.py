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
import re
import time
from dataclasses import dataclass, field
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

# Set of rarities we treat as "chase" — high-variance, high-value variants
# that share a name with cheaper variants in the same set (e.g. Meowth ex
# SIR #121 shares name with Meowth ex DR #60). For chase rarities we:
#   1. Require the card number in the listing title (regex word-boundary)
#   2. Apply a rarity-absolute price floor
#   3. Lower the min-listings threshold to 2 (chase supply is thin)
# We do NOT append the rarity word to the q-string anymore — eBay sellers
# inconsistently use abbreviations ("SIR" vs "Special Illustration Rare" vs
# nothing), and forcing it filtered out valid listings, leaving us with 0
# results for new cards like Meowth ex SIR in Perfect Order.
_CHASE_RARITIES = frozenset({
    "Special Illustration Rare",
    "Illustration Rare",
    "Hyper Rare",
    "Rare Rainbow",
    "Mega Hyper Rare",
})

# Price-sanity bounds for listings vs the card's TCGplayer reference price.
# eBay raw cards can run 30-90% of TCGplayer, sometimes 100-200%. Anything
# outside (0.30, 5.0) × TCG market is almost certainly a different card,
# a sealed product, or a typo. me2-125 SIR was returning $75 listings at a
# $808 reference — that's 9%, clearly wrong-card noise.
_PRICE_FLOOR_RATIO = 0.30
_PRICE_CEILING_RATIO = 5.0
_PRICE_FLOOR_ABS = 0.50  # never reject prices above 50¢ as "too low"
_PRICE_CEILING_ABS = 20.0  # never reject prices below $20 as "too high"

# Rarity-based price floors. Used when no TCGplayer reference is available
# (typical for brand-new Mega Evolution sets). SIRs/Hyper Rares essentially
# never sell below these floors — anything cheaper is the lower-rarity
# variant being misidentified. Tuned conservatively so genuine cheap chase
# cards (obscure Pokémon) still pass.
_RARITY_ABS_FLOOR = {
    "Special Illustration Rare": 5.0,
    "Illustration Rare": 2.0,
    "Hyper Rare": 5.0,
    "Rare Rainbow": 5.0,
    "Mega Hyper Rare": 10.0,
}

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
             pokemon Mega Charizard X ex 125/094 Phantasmal Flames
    Falls back gracefully when total/set is unknown.

    Note: `rarity` is accepted for API compatibility but no longer appended
    to the query string. eBay sellers don't consistently write rarity
    abbreviations, so forcing "SIR" into the query filtered out valid
    listings. Chase disambiguation happens post-fetch via card-number-in-
    title + rarity price floor instead.
    """
    parts: list[str] = ["pokemon", card_name.strip()]
    if card_number:
        num = card_number.strip()
        if printed_total and "/" not in num:
            num = f"{num}/{printed_total}"
        parts.append(num)
    if set_name:
        parts.append(set_name.strip())
    _ = rarity  # accepted but unused; see docstring
    return " ".join(p for p in parts if p)


@dataclass(frozen=True)
class FilterConfig:
    """Knobs that decide whether a single eBay listing passes the noise filter
    stack for `price_summary`. Pulled out so the same logic can be reused by
    the diagnostic inspect script and the test suite."""

    title_noise: tuple[str, ...] = field(default_factory=lambda: _TITLE_NOISE_DEFAULT)
    number_pattern: re.Pattern[str] | None = None
    sanity_floor: float | None = None
    sanity_ceiling: float | None = None


@dataclass(frozen=True)
class ListingClassification:
    """Verdict on one eBay item after the filter stack. `kept=True` items
    feed the aggregate; `kept=False` items carry the reason so the inspect
    script and snapshot logs can explain misses."""

    title: str
    price_usd: float | None
    currency: str
    url: str | None
    kept: bool
    drop_reason: str | None


def _classify_listing(item: dict, cfg: FilterConfig) -> ListingClassification:
    """Pure function. Same logic the snapshot uses internally — no I/O."""
    title_raw = item.get("title") or ""
    title_lc = title_raw.lower()
    url = item.get("itemWebUrl") or item.get("itemHref")

    for noise in cfg.title_noise:
        if noise in title_lc:
            return ListingClassification(
                title=title_raw, price_usd=None, currency="", url=url,
                kept=False, drop_reason=f"title_noise:{noise.strip()}",
            )

    if cfg.number_pattern and not cfg.number_pattern.search(title_lc):
        return ListingClassification(
            title=title_raw, price_usd=None, currency="", url=url,
            kept=False, drop_reason=f"missing_number:{cfg.number_pattern.pattern}",
        )

    p = item.get("price") or {}
    raw_currency = p.get("currency", "")
    try:
        v = float(p["value"])
    except (KeyError, TypeError, ValueError):
        return ListingClassification(
            title=title_raw, price_usd=None, currency=raw_currency, url=url,
            kept=False, drop_reason="no_price",
        )

    currency = raw_currency or "USD"
    if currency != "USD":
        return ListingClassification(
            title=title_raw, price_usd=v, currency=currency, url=url,
            kept=False, drop_reason=f"wrong_currency:{currency}",
        )
    if v <= 0:
        return ListingClassification(
            title=title_raw, price_usd=v, currency=currency, url=url,
            kept=False, drop_reason="price_zero",
        )
    if cfg.sanity_floor is not None and v < cfg.sanity_floor:
        return ListingClassification(
            title=title_raw, price_usd=v, currency=currency, url=url,
            kept=False, drop_reason=f"below_floor:{cfg.sanity_floor:.2f}",
        )
    if cfg.sanity_ceiling is not None and v > cfg.sanity_ceiling:
        return ListingClassification(
            title=title_raw, price_usd=v, currency=currency, url=url,
            kept=False, drop_reason=f"above_ceiling:{cfg.sanity_ceiling:.2f}",
        )

    return ListingClassification(
        title=title_raw, price_usd=v, currency=currency, url=url,
        kept=True, drop_reason=None,
    )


def _compute_aggregate(prices: list[float]) -> dict[str, Any]:
    """Pure aggregation: sort, IQR-light trim, return low/median/high.

    Caller must guarantee len(prices) >= 1.
    """
    prices = sorted(prices)
    n = len(prices)
    trim = n // 8 if n >= 8 else 0
    core = prices[trim : n - trim] if trim else prices
    m = len(core)
    median = (
        core[m // 2] if m % 2 else (core[m // 2 - 1] + core[m // 2]) / 2
    )
    return {
        "low": core[0],
        "median": median,
        "high": core[-1],
        "count_sampled": m,
    }


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
        card_number: str | None = None,
        rarity: str | None = None,
    ) -> dict[str, Any] | None:
        """Fetch fixed-price listings and compute low / median / high USD.

        Thin wrapper around `price_summary_with_trace` that returns only the
        aggregate summary (or None). For diagnostics use the traced version.
        """
        detail = await self.price_summary_with_trace(
            query,
            category_id=category_id,
            max_results=max_results,
            fixed_price_only=fixed_price_only,
            new_only=new_only,
            exclude_terms=exclude_terms,
            min_price_usd=min_price_usd,
            max_price_usd=max_price_usd,
            reference_price_usd=reference_price_usd,
            card_number=card_number,
            rarity=rarity,
        )
        return detail["summary"]

    async def price_summary_with_trace(
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
        card_number: str | None = None,
        rarity: str | None = None,
    ) -> dict[str, Any]:
        """Same as `price_summary` but also returns per-listing classification.

        Returns:
            {
              "summary": dict | None,                # same shape as price_summary
              "cleaned_query": str,                  # the actual query string sent to eBay
              "config": FilterConfig,                # the filter knobs that were applied
              "is_chase": bool,
              "min_required": int,                   # min listings needed to compute aggregate
              "passes": [                            # one entry per eBay call (1 or 2)
                {
                  "label": "fixed_price" | "auction_fallback",
                  "total_listings_hint": int,       # eBay's reported total
                  "classifications": [ListingClassification, ...],
                }
              ],
            }

        Used by both the snapshot (which discards the trace) and the inspect
        script (which renders it).
        """
        filters: dict[str, str] = {}
        if fixed_price_only:
            filters["buyingOptions"] = "FIXED_PRICE"
        if new_only:
            filters["conditions"] = "NEW"
        if min_price_usd is not None or max_price_usd is not None:
            lo = "" if min_price_usd is None else f"{min_price_usd:.2f}"
            hi = "" if max_price_usd is None else f"{max_price_usd:.2f}"
            filters["price"] = f"[{lo}..{hi}]"
            filters["priceCurrency"] = "USD"

        cleaned_query = build_query(query, exclude=exclude_terms)

        # Price-sanity bounds. Three layers compose:
        #   1. TCGplayer reference (relative band) — when we have it
        #   2. Rarity-based absolute floor — for chase rarities w/o TCG ref
        #   3. Conservative absolute floors/ceilings as last resort
        sanity_floor: float | None = None
        sanity_ceiling: float | None = None
        if reference_price_usd is not None and reference_price_usd > 0:
            sanity_floor = max(
                reference_price_usd * _PRICE_FLOOR_RATIO, _PRICE_FLOOR_ABS
            )
            sanity_ceiling = max(
                reference_price_usd * _PRICE_CEILING_RATIO, _PRICE_CEILING_ABS
            )
        if rarity and rarity in _RARITY_ABS_FLOOR:
            sanity_floor = max(sanity_floor or 0, _RARITY_ABS_FLOOR[rarity])

        is_chase = bool(rarity and rarity in _CHASE_RARITIES)
        require_number_in_title = bool(is_chase and card_number)
        number_token = (card_number or "").split("/")[0].strip()
        number_pattern = (
            re.compile(rf"\b{re.escape(number_token)}\b")
            if require_number_in_title and number_token
            else None
        )

        config = FilterConfig(
            title_noise=_TITLE_NOISE_DEFAULT,
            number_pattern=number_pattern,
            sanity_floor=sanity_floor,
            sanity_ceiling=sanity_ceiling,
        )

        async def _fetch_pass(
            active_filters: dict[str, str], label: str
        ) -> dict[str, Any]:
            res = await self.browse_search(
                cleaned_query,
                limit=max_results,
                filters=active_filters or None,
                category_id=category_id,
            )
            items = res.get("itemSummaries") or []
            classifications = [_classify_listing(it, config) for it in items]
            return {
                "label": label,
                "total_listings_hint": int(res.get("total") or 0),
                "classifications": classifications,
            }

        passes: list[dict[str, Any]] = []
        passes.append(await _fetch_pass(filters, "fixed_price"))
        kept_prices = [c.price_usd for c in passes[0]["classifications"] if c.kept and c.price_usd is not None]

        # Fallback for hot/new cards that are mostly auctions (e.g. Cinccino ex SIR):
        # if we got nothing under FIXED_PRICE, retry including auctions.
        if not kept_prices and fixed_price_only:
            relaxed = {k: v for k, v in filters.items() if k != "buyingOptions"}
            passes.append(await _fetch_pass(relaxed, "auction_fallback"))
            kept_prices = [c.price_usd for c in passes[-1]["classifications"] if c.kept and c.price_usd is not None]

        # Chase rarities get min 2 (thin supply); commons keep min 3 (single
        # PSA outlier protection).
        min_required = 2 if is_chase else _MIN_LISTINGS_FOR_PRICE

        summary: dict[str, Any] | None
        if len(kept_prices) < min_required:
            summary = None
        else:
            agg = _compute_aggregate(kept_prices)
            total_hint = max((p["total_listings_hint"] for p in passes), default=0)
            summary = {
                **agg,
                "total_listings": total_hint or len(kept_prices),
                "cleaned_query": cleaned_query,
            }

        return {
            "summary": summary,
            "cleaned_query": cleaned_query,
            "config": config,
            "is_chase": is_chase,
            "min_required": min_required,
            "passes": passes,
        }
