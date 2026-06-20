# PullList — Future Feature Ideas

Notebook of features harvested from competitor scans, support requests,
and product instincts. Nothing here is committed; treat as a candidate
pool to draw from when capacity opens up.

Each item has a quick triage:
- 🟢 **High leverage** — clearly differentiating or unblocks our stated future goal
- 🟡 **Solid** — well-known pattern, real value, no infra moat
- 🔵 **Polish** — UX-only, small wins, can ship in spare cycles
- ⚪ **Maybe never** — interesting but heavy or off-brand

---

## Data quality & price accuracy

These are the biggest "moat" wins. Wrong prices kill trust faster than missing features.

- 🟢 **Card-number strict matching on eBay listings** — extract `\d+/\d+` from each listing title, require numerator match to target card. Drops same-character different-print pollution (Meowth 062 listings flooded by 121 SIR). Direct prereq for wishlist price alerts.
- 🟢 **Set-total denominator match (Tier 2)** — also compare the `/total` part when present so different-set cards with the same number don't collide.
- 🟢 **Graded vs ungraded price separation** — PSA/BGS/CGC prices must live in their own buckets and not contaminate the median for raw cards. Detect via the `\b(psa|bgs|cgc|sgc)\s*\d` pattern we already use frontend-side.
- 🟢 **Cross-region contamination filter** — when computing US prices, drop listings whose titles mention "Japanese" or contain JP card numbers like SV5K-021. Same in reverse for the JP feed.
- 🟢 **Real-sale vs asking-price flag** — eBay sold listings vs active asks behave very differently. Tag each price point so the trend line can show "actual sales" overlay.
- 🟡 **Statistical outlier rejection** — already running median/tercile on snapshots; extend to per-listing rejection with IQR test before the price even hits the snapshot table.
- 🟡 **Variant-aware pricing (e.g. Pokeball / Masterball patterns)** — same card id but different reverse-holo treatment trades for very different prices. Either separate card rows or per-variant price tabs.
- 🟡 **Perceptual hash check** — pre-compute pHash on every card in catalog; compare against listing thumbnails. Catches sellers who mistyped the card number. Gold standard for the alert system but adds infra (storage + compute on ingest).

## Search & discovery

- 🟢 **Alias / nickname search** — "맥날츄" → McDonald's Pikachu, "고흐츄" → Van Gogh collab Pikachu. Curated list of community names per card.
- 🟢 **Typo correction / fuzzy match** — Levenshtein-1 fallback when exact match returns zero ("리자모" → "리자몽", "Charzard" → "Charizard").
- 🟡 **Spaceless query handling** — "피카츄ex" should match "Pikachu ex". Strip internal whitespace from both query and indexed name during compare.
- 🟡 **Cross-language name search** — searching the EN name should hit the JP/KR card, and vice versa. Backed by the language fields we already index.
- 🟡 **Card-number-only search** — bare "062" should hit "062/088" cards, not literal text matches in titles.
- 🟡 **Mega-evolution parent linking** — search "Charizard" returns "Mega Charizard ex" too. Already mostly works via substring; verify and gap-fill.
- 🟡 **Rarity keyword as landing page** — searching just "SAR" or "AR" routes to a curated rarity landing instead of a noisy substring match.
- 🔵 **Recent / popular searches sidebar** — surface what others are looking at, cheap engagement bump.

## Collection & portfolio

- 🟢 **Per-Pokemon collection view** — tap a Pokemon name in collection and get all KR/JP/US versions of that Pokemon laid out in a grid, owned bright / unowned dim. Encourages master-set chase.
- 🟢 **"Owned" badge in catalog browsing** — anywhere a card thumbnail appears (set page, search, trending), show a small 📦 if the logged-in user owns it. Big retention multiplier.
- 🟡 **Sharable per-Pokemon collection page** — auto-public when shared, signed URL.
- 🟡 **Master-set progress meter** — at the set page level, "you own 47/164 (29%) of this set". Already partially there.
- 🟡 **Graded-card conversion flow** — let user convert an owned raw card into a graded card row, adding grader fee to cost basis automatically (PSA, BGS, CGC, BRG service tiers).
- 🔵 **Owned-card filter on every list** — pin a "show only owned" toggle on trending, search, drops.

## Card detail enhancements

- 🟢 **Per-variant price tabs** — masterball pattern vs poke-ball pattern vs base — same card id, different treatments, very different prices. Tabs inside the price block.
- 🟡 **7-day delta badge** — `+12.4%` chip next to the headline price.
- 🟡 **Multi-grader price strip** — small horizontal row: Raw / PSA 10 / BGS 9.5 / CGC 9 with prices. One glance comparison.
- 🟡 **Image zoom / pinch** — click thumbnail to fullscreen with zoom controls. Mobile pinch supported.
- 🔵 **Card number copy button** — small icon next to the displayed number.

## Wishlist & price alerts (our stated future feature)

- 🟢 **Strict-match required** — only fire alert when listing `score == 100` (exact card_number/set_total match). Loose matches degrade trust instantly. Builds on the strict-matching foundation above.
- 🟢 **Per-card target price** — user sets "buy if drops below $X", we email/push when matched eBay listing falls under it.
- 🟢 **Direct buy link in the alert** — email or push includes affiliate-wrapped URL to that specific listing.
- 🟡 **Snooze / dismiss** — if a target is hit but user not ready, snooze 24h instead of demoting the alert.
- 🟡 **Multi-region alerts** — same alert can fire across KR/JP/US sources with currency conversion at delivery time.
- 🔵 **Alert digest mode** — opt out of realtime push, get a daily summary email instead.

## Trending & discovery

- 🟡 **Top Pokemon homepage shortcuts** — "Charizard / Pikachu / Mew / Mewtwo" tiles at top of home. Better discovery than naked search bar.
- 🟡 **Rarity landing pages** — `/r/sar`, `/r/sir`, `/r/ur` — SEO-friendly, gives a clear answer to "show me all SARs across all sets".
- 🔵 **Weekly trending top-30 leaderboard** — already have movers; extend to a persistent leaderboard with rank-change arrows.

## Multi-language & cross-region

- 🟢 **Cross-region price comparison on card detail** — for a card with KR/JP/US versions, show all three prices side by side with FX conversion. Direct arbitrage signal.
- 🟡 **hreflang sitemap entries** — `/en/...`, `/ja/...`, `/ko/...` urls in sitemap for search visibility abroad.
- 🟡 **Auto-translate set/Pokemon names** — currently partial; build out the gap-fill so no Korean leaks into the EN/JP catalog views.
- 🔵 **Per-user default currency** — show all prices in user's preferred currency, not always USD.

## Engagement features (games)

Probably worth doing one of these for retention; multiple is overkill.

- 🟡 **Daily free pack opening** — pick a random card from a curated rarity pool (RR+), one per day per user. Pure dopamine, brings users back.
- 🟡 **Price guessing game** — "which is more valuable: card A or card B?" Two thumbnails, score on streak. Cheap to build, hooks for sharing.
- 🟡 **Streak leaderboard** — top 30 weekly, rank-up arrows.
- 🔵 **Daily check-in reward** — 5-day streak grants something (free pack draw, premium day pass).
- 🔵 **Pokemon-trivia onboarding mission** — "follow 3 collectors, register 5 cards, set 1 wishlist alert" → free 1-day premium.

## Marketplace & social

These are deep features — only after the catalog moat is built.

- ⚪ **Buy-offer system** — "I'd pay $X for this card you own" → owner accepts or counter-offers. Owner identity stays private until accepted. Big trust/legal infra.
- ⚪ **Auction listing** — sellers list with reserve price, others bid, auto-close at deadline.
- ⚪ **In-app messaging** — for buyer/seller comms with image attachment for card condition shots.
- ⚪ **Follow / followers** — other collector profiles, see their collection.
- ⚪ **News / community feed** — articles, comments, likes. We're a catalog, not a forum.

## Notifications

- 🟢 **Price-change push** — already on the roadmap via wishlist alerts. Web push first, mobile later.
- 🟡 **Listing-appeared push** — for cards with zero active listings, ping when a new one appears.
- 🔵 **Wishlist digest email** — weekly summary of price action on your wishlist.

## VIP / monetization

- 🟡 **Ad-free tier** — basic VIP with no ads + small badge. Easy to ship once Stripe is wired.
- 🟡 **Premium features paywall** — alerts beyond N cards, advanced filters, CSV exports beyond N rows.
- 🟡 **VIP-only insights** — graded-card spread, predicted-30-day price, watchlist trend report.
- 🔵 **Day-pass / weekly-pass micro-purchases** — for users who don't want monthly subscription.

## UI polish

- 🔵 **Dark-mode table contrast** — verify all tables read cleanly in dark mode.
- 🔵 **Image lightbox with zoom** — click any card image for fullscreen + zoom + drag.
- 🔵 **KakaoTalk / X share previews** — rich card with image and price in OG tags.
- 🔵 **Onboarding tutorial** — first-time users get a 30-second tour of the main panels.

## Calendar & events

- 🔵 **TCG event calendar** — card shows, official tournaments, set release dates. Light data ops to maintain.

## Mobile

- ⚪ **Native Android app** — only after web product proves out and traction justifies maintenance burden.
- ⚪ **iOS app** — same gating, but Apple's review overhead doubles the cost.

---

## Prioritization signal

If a roadmap conversation needs a single ordered pick-list to argue from:

1. Card-number strict matching (eBay filter) — direct prereq for wishlist alerts, immediate quality win on the live-listings panel.
2. Graded/raw price separation — trust foundation, blocks any serious user from relying on our prices.
3. "Owned" badge in catalog browsing — retention multiplier, almost zero infra.
4. Per-Pokemon collection view — differentiator and shareable.
5. Daily free pack opening — engagement loop, cheap to build, hooks for organic growth.
6. Cross-region price comparison on card detail — leans into our KR/JP/US coverage as a moat.
7. Wishlist with price alerts (strict-match required) — the stated future flagship.
8. Per-variant price tabs (masterball / pokeball etc.) — fixes a real catalog gap.
9. Multi-grader price strip on card detail — clarifies the most-asked question.
10. Alias / nickname / typo search — quality-of-life that compounds over time.

Everything below that is opportunistic — pick what fits the current sprint's theme.
