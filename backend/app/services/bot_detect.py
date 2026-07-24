"""User-Agent → bot name mapping.

Extract the identifier of a known crawler from a raw User-Agent header
without persisting the full UA. Used by `/api/visits` to populate
`visit_logs.bot_name` and by `/admin/visits/bots` to aggregate crawler
traffic.

Adding a new bot: append `(name, compiled_regex)` to BOT_PATTERNS in
the right group. Order matters — the first match wins, so specific
patterns must come before the generic-bot fallback.
"""

import re

# (name, regex) tuples, matched in order. First hit wins.
BOT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ── Search engines (allowed by default in robots.txt) ────────
    ("Googlebot-Image", re.compile(r"Googlebot-Image", re.I)),
    ("Googlebot", re.compile(r"Googlebot(?!-Image)", re.I)),
    ("Bingbot", re.compile(r"Bingbot", re.I)),
    ("DuckDuckBot", re.compile(r"DuckDuckBot", re.I)),
    ("YandexBot", re.compile(r"YandexBot", re.I)),
    ("NaverBot", re.compile(r"Yeti", re.I)),
    ("Applebot", re.compile(r"Applebot(?!-Extended)", re.I)),

    # ── LLM training / AI answer bots (typically blocked) ────────
    ("GPTBot", re.compile(r"GPTBot", re.I)),
    ("ChatGPT-User", re.compile(r"ChatGPT-User", re.I)),
    ("OAI-SearchBot", re.compile(r"OAI-SearchBot", re.I)),
    ("ClaudeBot", re.compile(r"ClaudeBot", re.I)),
    ("anthropic-ai", re.compile(r"anthropic-ai", re.I)),
    ("Google-Extended", re.compile(r"Google-Extended", re.I)),
    ("Applebot-Extended", re.compile(r"Applebot-Extended", re.I)),
    ("CCBot", re.compile(r"CCBot", re.I)),
    ("PerplexityBot", re.compile(r"PerplexityBot", re.I)),
    ("Amazonbot", re.compile(r"Amazonbot", re.I)),
    ("Bytespider", re.compile(r"Bytespider", re.I)),
    ("Diffbot", re.compile(r"Diffbot", re.I)),

    # ── 3rd-party SEO crawlers (typically blocked) ───────────────
    ("AhrefsBot", re.compile(r"AhrefsBot", re.I)),
    ("SemrushBot", re.compile(r"SemrushBot", re.I)),
    ("DotBot", re.compile(r"DotBot", re.I)),
    ("PetalBot", re.compile(r"PetalBot", re.I)),
    ("DataForSeoBot", re.compile(r"DataForSeoBot", re.I)),
    ("MJ12bot", re.compile(r"MJ12bot", re.I)),
    ("BLEXBot", re.compile(r"BLEXBot", re.I)),

    # ── Social / preview crawlers ────────────────────────────────
    ("facebookexternalhit", re.compile(r"facebookexternalhit", re.I)),
    ("Twitterbot", re.compile(r"Twitterbot", re.I)),
    ("Discordbot", re.compile(r"Discordbot", re.I)),
    ("Slackbot", re.compile(r"Slackbot", re.I)),
    ("TelegramBot", re.compile(r"TelegramBot", re.I)),
    ("WhatsApp", re.compile(r"WhatsApp", re.I)),

    # ── Monitoring / uptime ──────────────────────────────────────
    ("UptimeRobot", re.compile(r"UptimeRobot", re.I)),
    ("Pingdom", re.compile(r"Pingdom", re.I)),

    # ── Fallback: unknown crawlers matching bot|spider|crawl ─────
    ("generic-bot", re.compile(r"\bbot\b|\bspider\b|\bcrawl(er)?\b", re.I)),
]


def detect_bot(user_agent: str | None) -> str | None:
    """Return the canonical bot name for a known crawler UA, else None.

    Never returns unknown or partial matches — only the fixed set of
    labels above ever hits the database, so no PII from arbitrary UA
    strings leaks into visit_logs.bot_name.
    """
    if not user_agent:
        return None
    for name, pattern in BOT_PATTERNS:
        if pattern.search(user_agent):
            return name
    return None
