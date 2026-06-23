# PullList — Project Status

**Last meaningful update**: 2026-06-22

Authoritative reference for what's been built, what's in progress, what's
planned, and the architectural decisions behind it. Maintained as a flat
markdown so any future session can land on the project and understand the
state in ~10 minutes.

---

## 1. What this is

PullList is a Pokémon TCG **collector platform** — catalog, collection
tracker, real-time market data — covering English, Japanese, and Korean
catalogs in one place. Friends-beta now; subscription tier planned once
core platform stabilizes.

- **Production**: https://pulllist.org
- **Repo**: `pulllistapp-stack/pulllist` (private)
- **Stage**: friends-beta
- **Audience target**: serious Pokémon TCG collectors — multilingual
  (EN/JP/KR), the underserved segment most tools ignore
- **Differentiator vs Pokefy / PriceCharting**: JP catalog is a
  first-class citizen with native rarity tiers; cross-language card
  matching ("Charizard" → リザードン → 리자몽 surface together)

---

## 2. Strategic decisions (locked in)

| # | Decision | Why |
|---|---|---|
| Positioning | **Collector platform**, not a Pokefy alternative | Different category, no head-on competition |
| Pricing | **$5.99/mo or $59/year** for future Pro tier | Undercut Pokefy ($8 alert-only) with broader platform value |
| Payments | **Lemon Squeezy** (MoR) for global, plus Korean PG later | Tax handled by MoR, simple |
| Tax structure | Korean **개인사업자 간이과세자** + Lemon Squeezy MoR | Hands-off VAT, focus on building |
| Catalog scope | **EN + JP + KR** unified | Real moat; competitors are EN-first |
| Catalog source | pokemontcg.io (EN) + TCGdex (JP) + Bulbapedia (JP rarity) | Free, legal, well-maintained |
| Pricing source | **TCGCSV daily archive** (primary) + eBay live + pokemontcg.io fallback | Fresher than pokemontcg.io alone |
| Mobile | PWA first → Google Play $25 later | Phased, $0 to start |
| Card scan | Claude Haiku 4.5 vision API | Simple, accurate, ~$0.003/scan |

---

## 3. Built — current state

### 3.1 Foundation
- **Next.js 16** (App Router, React 19) frontend → Vercel
- **FastAPI + SQLAlchemy 2.0 async + asyncpg** backend → Render
- **Neon Postgres** (Free tier — 512 MB; cleanup applied)
- **JWT auth** (signup / login / Google OAuth) with rate-limited + honeypotted signup
- **Admin role** (`users.is_admin`) + soft delete (`users.deleted_at`)
- DM Sans + JetBrains Mono fonts
- Light/dark theme via CSS variables, `next-themes`
- Site-wide footer (text wordmark), 4-card Contact page, Privacy/Terms/About

### 3.2 Catalog & data
- **31,000+ cards** (EN 20,668 + JA 10,970)
- **340+ sets** (EN 173 + JA 171 — including all JP promo eras JPP-XY/SwSh/SM/SV/S)
- Card detail page: hero with 3D-tilt sparkle hover, price chart, secondary prices, live listings, breadcrumb, neighbors, per-variant tabs
- Card image magnifier loupe (hover, portal-mounted to escape transform contexts)
- Set detail page: hero with logo, completion progress, set-scoped filter chips, card grid
- Cards browse with sidebar filter (FilterSidebar): rarity / supertype / energy / subtype / set / artist / HP / price / condition / owned
- **Bulbapedia** (CC-BY-SA) set logos / promo era covers
- **japon-collection.com** logos for SwSh-era JP sets (38 of 59)
- **Limitless** fallback for JP card images where TCGdex returns null
- **Per-variant pricing** — `cards.tcgplayer_prices` JSON stores normal / holofoil / reverseHolofoil / 1stEdition / 1stEditionHolofoil / unlimited / unlimitedHolofoil with low / mid / high / market / directLow

### 3.3 Pricing pipeline
- **TCGplayer**: Primary daily refresh from **TCGCSV** (`api.tcgcsv.com`),
  fallback weekly from pokemontcg.io. The archive backfill brought in
  ~80 days of dense history.
- **eBay Browse API** (production credentials, live + daily snapshots)
- **Portfolio daily valuation snapshots** (per-user roll-up)
- **GitHub Actions cron**:
  - `daily-ebay-snapshot.yml` (03:00 UTC, 90min timeout)
  - `daily-tcgplayer-sync.yml` (08:00 UTC — runs TCGCSV first, then
    pokemontcg.io with `--cardmarket-only`)
  - `daily-portfolio-snapshot.yml` (05:00 UTC, 30min timeout)
- **Listing match filter** (`backend/app/services/listing_match.py`):
  - Score 100/70/30/0 by card number, name, accessory denylist
  - Seller trust tier (TRUSTED sellers exempt from suspicious filter)
  - Ultra-low price floor (rarity-based)
  - 3-layer sanity check for snapshot price (rarity floor, market-relative band, sales count ≥ 2)
- **Snapshot retention** (`compress_snapshots.py`):
  - 0-7d: daily
  - 8-30d: weekly
  - 31-90d: monthly
  - 91-365d: monthly
  - 366d+: deleted
  - One-shot `storage_cleanup.py` reclaimed 323 MB (cardmarket drop + VACUUM FULL)

### 3.4 Collection management
- **CollectionItem** model (condition, grade, qty, acquired_at, notes, variant)
- **WishlistItem** model (priority, max_price_usd, notes, variant)
- **PortfolioSnapshot** model (daily valuation history per user)
- **Per-variant collection** — same card can be owned in multiple variants (e.g. normal + holofoil)
- One-tap "I have this" toggle on every card
- Heart toggle for wishlist on every thumbnail
- Wishlist target price modal (priority, target $, notes, live "at target" hint)
- Portfolio page: stats grid, asset mix donut, growth chart (SVG area), Top 10 by value, full vault grouped by set
- CSV export of collection

### 3.5 Trending
- 7d / 30d / 90d windows (1d removed — daily cron can't produce 2+ snapshots/day; saved for Phase 2 with hourly cron)
- **Bulk / Chase tier split** — Common-to-Double-Rare vs Ultra-and-up + promos; default-tab "All" or filter
- **Bubble-outlier filter** — `min_snapshots` auto-scales by period, MAD-ratio cap, step-function detector, 200% delta cap
- Top 3 podium (gold/silver/bronze), mover rows with sparklines, period+source+direction filters, $1/$5/$10/$50 floor

### 3.6 Search
- **Cross-language search** — `_expand_query_to_dex_numbers` looks up
  national_pokedex_numbers on solo-Pokémon name matches, then expands
  to all-language cards sharing those dex IDs.
- "Charizard" surfaces EN Charizard + ja-リザードン + ko-피카츄 (correct
  Pokémon for each language)
- Single-Pokémon filter prevents tag-team contamination (Reshiram &
  Charizard-GX doesn't drag every solo Reshiram into a Charizard
  search)
- Dex backfill via PokéAPI multi-lang name index (3,952 JP/KR cards
  matched, 1,198 unmatched = Trainer/Energy/stylized promo names)

### 3.7 Rarity color system
- `lib/rarity.ts` — single source of truth for tier classification
- 13 tiers (common / uncommon / rare / holo / ultra / illustration / sir / mega / hyper / shiny / secret / promo / ace / other)
- Each tier has inactive + active styling
- Used by FilterSidebar chips, CardThumb labels, Trending rows, card detail header, scan results

### 3.8 Mobile / PWA
- `public/manifest.json` + `sw.js` + `PWARegister` client
- Add-to-home-screen on iOS Safari / Android Chrome
- Theme-color metadata for both modes
- Apple touch icon (smooth logo)
- **Card scanning** (`/scan` page):
  - Mobile-only camera (`md:hidden`); desktop shows QR fallback
  - Full-screen camera with TCG-aspect targeting overlay
  - Flashlight toggle (when supported)
  - Claude Haiku 4.5 vision → JSON identification
  - 3-tier DB fuzzy match (name+number+set → name+number → name)
  - Top 5 candidates with rarity chip + price + one-tap Add
- **ScanFAB** — floating yellow button bottom-right, mobile-only, hidden on `/scan`, `/login`, `/signup`, `/cards/*`

### 3.9 Homepage & marketing
- Auth-aware HeroCTA (logged-out: signup; logged-in: portfolio + scan)
- Hero mascot: smooth duo illustration (pixel reserved for loading)
- Trending strip (top 4 movers from /cards/trending)
- Latest sets section
- Feature pillars (Catalog / Live prices / History)
- Final CTA with mascot sparkles
- Stats reflect actual catalog: **31,000+ cards** / **340+ sets** / **Daily price snapshots**
- Pill banner: "EN · JP · KR catalogs"

### 3.10 Mascot loaders
- 4 animated APNGs from PixelLab (idle, fly, pack, sleep)
- `<MascotLoader>` component picks one at random per mount (SSR-safe — initial idle, swap after hydration)
- Rotating English status phrases (Counting your pulls / Calling the trainer / Checking the prices)
- Applied at: route transitions (`app/loading.tsx`), trending data fetch, cards browse, portfolio loading, wishlist auth gate, admin auth check
- Hero + TopNav logo uses smooth Dragonite illustration; pixel art lives in loading-only moments

### 3.11 Portfolio sharing
- Non-enumerable share_token URL: `/p/[24-char-base64url]`
- Opt-in public mode (default private)
- Per-section toggles: value / growth / wishlist / all_cards
- Token rotation (invalidates old URL)
- ShareModal on `/portfolio` with copy + rotate
- Public viewer renders mascot avatar + display name + bio + stats + asset mix + top 20 cards + set completion + optional growth/wishlist/full grid
- "Create your own" CTA at bottom for viral pull
- Open Graph metadata + auto-generated OG image card

### 3.12 News / Articles (in-DB)
- Posts live in `news_posts` table (DB-backed, NOT filesystem markdown)
- Author + edit + delete from `/admin/news` — no git push needed
- **Categories** (6): Drops / Market / Pokémon TCG / Pokémon Center / Guide / News
- Region field on DB row (forward-flexibility) but UI uses category tabs
- Listing page: tabbed by category, grouped by date, thumbnail + view count + read time
- Detail page: full Markdown render (react-markdown + remark-gfm)
- **View counter** — `news_views` table, anonymous, deduped per tab via sessionStorage

### 3.13 Admin panel
- `/admin/news` — list, create, edit, delete posts (Markdown body, category dropdown)
- `/admin/users` — paginated user list, search, include-deleted toggle, role chip, card+wishlist counts, Promote/Demote, Soft Delete, Restore
- Self-action guards (admin can't demote or delete themself)
- Shared `<AdminNav>` strip (News / Users)
- `<AdminGuard>` wraps each page — client redirect for non-admins
- Backend `get_current_admin` dependency — 403 for non-admins
- Edge middleware on `/admin/*` — noindex + no-store headers
- Admin chip in TopNav next to avatar (only visible when `user.is_admin`)

### 3.14 Affiliate / monetization
- **TCGplayer affiliate** via Impact — approved, 3.5% commission. Direct-link params hardcoded as default in `affiliate.ts` (`irpid=7410135`). Every outbound TCGplayer link wrapped automatically.
- **eBay Partner Network** — live. Campaign `5339157076` (default) Active in EPN; `NEXT_PUBLIC_EBAY_CAMPAIGN_ID` wired in Vercel; every outbound eBay link wrapped with campid + toolid + mkrid. Contract: 1–4% per item, 24h referral window.
- **Google AdSense** — site verified (`ca-pub-9440218369165896`), under review. Compliance pass landed (privacy policy disclosure, ads.txt, /contact page).
- "Buy on TCGplayer" buttons throughout card detail (auto-tracked)
- Affiliate disclosure in Footer + Privacy

### 3.15 Anti-bot Phase 1 (just shipped)
- **Honeypot** field (`website`) — off-screen, aria-hidden, tabIndex=-1
- **Per-IP rate limit** — 5 signups per rolling hour, in-memory deque per IP
- **Disposable email blocklist** — frozenset of ~60 throwaway providers (mailinator, guerrillamail, tempmail variants, etc.)
- All applied to `/auth/signup` before any DB touch
- Phase 2 (email verification via Resend) and Phase 3 (CAPTCHA, phone verification) deferred

### 3.16 Auxiliary projects
- **TargetBot** (separate repo) — Patchright stealth bot for Target restock + auto-buy. Domain-knowledge source for anti-bot work in future PullList alert pipeline.

---

## 4. Pricing & business model — current plan

```
PullList Free  $0 forever
  Catalog (31,000+ cards) · Collection tracker · Wishlist
  Portfolio + growth chart · Trending · Price history (7d/30d/90d/1y)
  Cross-language search · Card scanning (5/day — limit not enforced yet)
  Public portfolio sharing
  Ads (Google AdSense, post-approval)

PullList Pro  $5.99/mo  or  $59/year  (NOT LIVE YET)
  Ad-free experience
  Wishlist target-price alerts (Email + push)
  Daily portfolio digest email
  Unlimited card scanning
  CSV / Excel import (export is free)
  Custom price alerts ("Chaos Rising SIR drops 15%")
  Multiple portfolios
  Detailed analytics (1y/5y charts, full snapshot history)
  Higher Trending API rate limits
  Early access to new features
```

Affiliate income: **TCGplayer 3.5%** (live) + **eBay Partner Network**
(live, 1–4% per item, 24h cookie).

Ad income: **Google AdSense** + **Mediavine / Ezoic** later (when traffic
crosses 10k MAU).

---

## 5. Planned — roadmap

### Now (immediate)
- [ ] Grant LO admin (1 SQL UPDATE in Neon)
- [ ] Wait for AdSense review (1-14 days; auto-resolves)
- [ ] LO: rotate the PixelLab API key (was exposed in chat)
- [ ] First 5-10 news posts to bulk up text content for AdSense review

### Sprint 1 (current)
- [ ] Email verification (Resend) — anti-bot Phase 2
- [ ] Wishlist target-price email alerts
- [ ] Daily portfolio digest email
- [ ] Sentry error monitoring (frontend + backend)
- [ ] Search includes Korean set names (TaskList #8)
- [ ] "Special Rare" / "Character Super Rare" / "Character Holo Rare"
      frontend RARITY_GROUPS classification
- [ ] Portfolio / Wishlist variant chips on owned items

### Sprint 2
- [ ] LemonSqueezy integration (Subscription model + webhooks)
- [ ] Pro tier gating middleware
- [ ] `/pricing` page polish (compare table updated)
- [ ] Scan daily rate-limit enforcement (5/day free, unlimited Pro)
- [ ] User Settings page (notification prefs, alert channels)

### Sprint 3+
- [ ] **Phase 1 full archive backfill** (91-365d range) — gated on Neon
      Launch tier upgrade
- [ ] In-store predictive restock monitors (Best Buy → Costco → GameStop)
- [ ] Discord webhook + Email alert delivery
- [ ] Trainer / Energy card cross-language mapping (Lillie ↔ リーリエ etc.)
- [ ] Expo (React Native) build for Google Play Store ($25 one-time)
- [ ] Trade calculator
- [ ] Wishlist sharing (separate token)
- [ ] Friend connections / collection comparison
- [ ] **Korean catalog** (KREAM pricing, pokemonkorea.co.kr name scrape)

### Future / not committed
- [ ] Apple App Store ($99/yr) — gate behind ~$500/mo MRR
- [ ] Auto-buy integration with retailer accounts (legally gray)
- [ ] PSA / BGS graded-slab tracking (Slab Trending tier)
- [ ] eBay sold-listings (Finding API) accuracy upgrade
- [ ] Other TCGs (Magic via Scryfall, One Piece, Lorcana, Yu-Gi-Oh)
- [ ] User-submitted price corrections (crowdsourcing)
- [ ] Tournament event tracking / deck builder integration
- [ ] **Mercari / Yahoo Auctions JP integration** — when truly serious about JP market analytics
- [ ] **Korean 사업자 등록** + **Stripe / Lemon Squeezy live** — gated on Pro tier demand signal
- [ ] DB migration to Render Postgres (when Neon free becomes untenable)

---

## 6. Known quirks / non-bugs

| Issue | Why it's not a bug | Workaround |
|---|---|---|
| New Mega Evolution sets show no TCGplayer prices | pokemontcg.io has 1-2 week lag for new sets | eBay fills the gap; rarity-floor sanity guards |
| Trending page shows nothing for ~24h after deploy | Need 2+ snapshots of same (card, source, variant) for delta calculation | Wait one day after cron starts |
| Render free-tier cold start can take 30-50s | Backend free tier behavior | Workflow timeouts 90min; SSR pages tolerate |
| Safari iOS doesn't expose camera torch | Browser-level limitation | Torch toggle silently hidden when unsupported |
| TCGplayer direct API is closed to new applicants | Post-eBay acquisition policy | Use pokemontcg.io + TCGCSV |
| eBay daily quota (5,000/day on free tier) | API limit | `snapshot_ebay.py --max-calls 4500` with throttle |
| ads.txt status "not found" right after deploy | Apex `pulllist.org` 308-redirects to `www.pulllist.org`; AdSense crawler takes days to follow | Wait 1-4 weeks, or set apex as Vercel primary domain |
| 1y trending chart is sparse | TCGCSV backfill only covers ~80 days back; remainder fills naturally via daily cron | Will be full a year after first deploy, or run full TCGCSV backfill on Neon Launch tier |
| 1d trending tab removed | Daily cron produces at most 1 snapshot/day → 1d window can't generate movers | Hourly cron is the fix; deferred until traffic justifies the Render bill |
| Trainer / Energy cards don't cross-language match | They have no dex_id → expansion can't link them across languages | Phase-2 task: manual mapping table for top ~50 trainer cards + 9 energies |

---

## 7. Tech stack reference

| Layer | Stack |
|---|---|
| Frontend framework | Next.js 16 (App Router), React 19 |
| Styling | Tailwind CSS 3, lucide-react icons, next-themes |
| Charts | Custom SVG (no library) |
| Markdown | react-markdown + remark-gfm |
| Backend framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 async |
| Database | Neon Postgres (production), SQLite (local dev) |
| HTTP client | httpx (backend), native fetch (frontend) |
| Auth | JWT (python-jose) + bcrypt password hashing |
| LLM | Claude Haiku 4.5 (Vision for card scan) via `anthropic` SDK |
| Pixel-art tools | PixelLab MCP (mascots) |
| Cron / scheduling | GitHub Actions (free tier) |
| Deploy: frontend | Vercel (free tier) |
| Deploy: backend | Render (free tier — paid Pro when traffic justifies) |
| Ads | Google AdSense (under review) |
| Affiliate | impact.com (TCGplayer, approved), eBay Partner Network (approved) |
| External APIs | pokemontcg.io, TCGCSV, TCGdex, eBay Browse, Anthropic, Bulbapedia, PokéAPI |
| PWA | Manual manifest + service worker (no `next-pwa` plugin) |

---

## 8. Environment variables

**Backend (Render)**:
- `DATABASE_URL` — Neon Postgres connection string
- `EBAY_APP_ID`, `EBAY_CERT_ID` — eBay Browse API credentials
- `EBAY_ENV=production`
- `ANTHROPIC_API_KEY` — Claude API key (for scanning)
- `POKEMONTCG_API_KEY` — optional, bumps rate limit
- `JWT_SECRET` — symmetric key
- `CORS_ORIGINS` — comma-separated allowed origins

**Frontend (Vercel)**:
- `NEXT_PUBLIC_API_BASE` — backend URL
- `NEXT_PUBLIC_TCGPLAYER_AFFILIATE_PARAMS` (optional — defaulted in code to LO's Impact params)
- `NEXT_PUBLIC_EBAY_CAMPAIGN_ID` — EPN campaign id (currently `5339157076`, default campaign Active)

**Local dev (`.env`, gitignored)**:
- All of above; also `LOG_LEVEL=DEBUG`

---

## 9. Admin operations

### One-time: grant LO admin
```sql
UPDATE users SET is_admin = TRUE WHERE email = 'YOUR_EMAIL';
```
Run in Neon SQL Editor. Log out + back in for the JWT to refresh.

### Day-to-day admin
- `/admin/news` → write posts (Markdown body, category dropdown)
- `/admin/users` → manage members (Promote/Demote/Delete/Restore)
- Neon SQL Editor only for one-off data fixes or stats

### Useful Neon SQL queries

**User stats**:
```sql
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE is_admin) AS admins,
       COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) AS deleted,
       COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS new_week
FROM users;
```

**Active collectors**:
```sql
SELECT u.email, COUNT(c.id) AS cards
FROM users u
LEFT JOIN collection_items c ON c.user_id = u.id
GROUP BY u.id, u.email
ORDER BY cards DESC LIMIT 20;
```

**Snapshot table size + counts by source**:
```sql
SELECT source, COUNT(*) FROM card_price_snapshots GROUP BY source;
```

---

## 10. Key file structure

```
pulllist/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── admin.py              # users CRUD (admin-only)
│   │   │   ├── auth.py               # signup / login / Google / me
│   │   │   ├── collection.py
│   │   │   ├── filters.py
│   │   │   ├── news.py               # posts CRUD + view counter
│   │   │   ├── routes.py             # /cards/* + /trending + /live-listings
│   │   │   ├── scan.py
│   │   │   ├── sharing.py
│   │   │   └── wishlist.py
│   │   ├── models/
│   │   │   ├── card.py
│   │   │   ├── collection.py
│   │   │   ├── news_post.py          # in-DB articles
│   │   │   ├── news_view.py          # view counter
│   │   │   ├── portfolio.py
│   │   │   ├── set.py
│   │   │   ├── snapshot.py
│   │   │   ├── user.py               # + is_admin, + deleted_at
│   │   │   └── wishlist.py
│   │   ├── services/
│   │   │   ├── anti_spam.py          # honeypot + rate limit + disposable
│   │   │   ├── ebay_client.py
│   │   │   ├── listing_match.py
│   │   │   └── variant_pricing.py
│   │   ├── schemas/
│   │   ├── auth.py                   # JWT + get_current_admin
│   │   ├── main.py
│   │   └── database.py
│   ├── scripts/
│   │   ├── backfill_jp_rarity.py
│   │   ├── backfill_jp_rarity_bulbapedia.py
│   │   ├── backfill_pokedex_numbers.py
│   │   ├── backfill_tcg_history.py
│   │   ├── backfill_tcgcsv_archive.py
│   │   ├── compress_snapshots.py
│   │   ├── import_jp_catalog.py
│   │   ├── import_jp_promos.py
│   │   ├── import_japon_logos.py
│   │   ├── migrate_add_variant_column.py
│   │   ├── migrate_markdown_news.py   # one-shot: is_admin/deleted_at ALTERs + post seed
│   │   ├── scrape_limitless_jp.py
│   │   ├── scrape_limitless_promos.py
│   │   ├── seed_promo_eras.py
│   │   ├── seed_sets.py
│   │   ├── snapshot_ebay.py
│   │   ├── snapshot_portfolios.py
│   │   ├── storage_cleanup.py
│   │   ├── sync_tcgcsv_daily.py       # primary daily TCGplayer
│   │   └── sync_tcgplayer_prices.py   # pokemontcg.io (cardmarket-only flag)
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── admin/
│   │   │   ├── news/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── new/page.tsx
│   │   │   │   └── [slug]/edit/page.tsx
│   │   │   └── users/page.tsx
│   │   ├── cards/[id]/page.tsx
│   │   ├── cards/page.tsx
│   │   ├── contact/page.tsx
│   │   ├── login/page.tsx
│   │   ├── news/page.tsx
│   │   ├── news/[slug]/page.tsx
│   │   ├── news/[slug]/view-bumper.tsx
│   │   ├── p/[token]/page.tsx
│   │   ├── portfolio/page.tsx
│   │   ├── pricing/page.tsx
│   │   ├── privacy/page.tsx
│   │   ├── scan/page.tsx
│   │   ├── search/page.tsx
│   │   ├── sets/page.tsx
│   │   ├── sets/[id]/page.tsx
│   │   ├── signup/page.tsx           # + honeypot
│   │   ├── terms/page.tsx
│   │   ├── trending/page.tsx
│   │   ├── wishlist/page.tsx
│   │   ├── about/page.tsx
│   │   ├── error.tsx
│   │   ├── loading.tsx               # MascotLoader on route transitions
│   │   ├── layout.tsx                # AdSense script + providers + middleware-aware
│   │   ├── page.tsx                  # home
│   │   ├── robots.ts
│   │   └── sitemap.ts
│   ├── middleware.ts                 # noindex /admin/*
│   ├── components/
│   │   ├── admin/
│   │   │   ├── AdminGuard.tsx
│   │   │   ├── AdminNav.tsx
│   │   │   └── PostForm.tsx
│   │   ├── card/
│   │   │   ├── ImageMagnifier.tsx
│   │   │   ├── LiveListings.tsx
│   │   │   ├── PullListCardDetail.tsx
│   │   │   └── VariantTabs.tsx
│   │   ├── portfolio/
│   │   │   └── ShareModal.tsx
│   │   ├── scan/
│   │   │   └── CardScanner.tsx
│   │   ├── AuthProvider.tsx
│   │   ├── CollectionProvider.tsx
│   │   ├── WishlistProvider.tsx
│   │   ├── FilterSidebar.tsx
│   │   ├── CardThumb.tsx
│   │   ├── MascotLoader.tsx          # 4-pose random APNG
│   │   ├── PortfolioGrowthChart.tsx
│   │   ├── AssetMixDonut.tsx
│   │   ├── RarityChip.tsx
│   │   ├── ScanFAB.tsx
│   │   ├── PWARegister.tsx
│   │   ├── Footer.tsx                # text wordmark
│   │   └── TopNav.tsx                # + Admin chip
│   ├── lib/
│   │   ├── affiliate.ts              # TCGplayer Impact params hardcoded
│   │   ├── api.ts
│   │   ├── auth.ts                   # + honeypot
│   │   ├── news.ts                   # API client + CATEGORIES
│   │   ├── rarity.ts
│   │   ├── variant.ts                # per-variant pricing helpers
│   │   └── utils.ts
│   ├── public/
│   │   ├── ads.txt                   # AdSense ownership declaration
│   │   ├── pullist-mascot.png        # idle APNG (loading)
│   │   ├── pullist-mascot-fly.png    # fly APNG (loading)
│   │   ├── pullist-mascot-pack.png   # pack APNG (loading)
│   │   ├── pullist-mascot-sleep.png  # sleep APNG (loading)
│   │   ├── pullist-mascot-logo.png   # smooth duo (hero + favicon)
│   │   ├── manifest.json
│   │   └── sw.js
│   ├── next.config.mjs
│   └── package.json
├── .github/
│   └── workflows/
│       ├── daily-ebay-snapshot.yml
│       ├── daily-tcgplayer-sync.yml      # TCGCSV first, pokemontcg.io --cardmarket-only second
│       └── daily-portfolio-snapshot.yml
└── PROJECT_STATUS.md
```

---

## 11. Recent journey (so future-me has context)

Rough chronological summary of major work landed in this push:

1. **Catalog expansion** — added JP catalog (TCGdex + Limitless + Bulbapedia rarity), grew from 12k EN to 31k EN+JP, added JP promo eras and SwSh-era logos
2. **Per-variant pricing refactor** — Option C rewrite, `collection_items.variant`, `wishlist_items.variant`, variant tabs UI, variant-aware suspicious filter
3. **Trending overhaul** — bubble outlier filter (snapshot density + step-function detector + 200% cap), tier split (Bulk vs Chase), 1d removed
4. **Cross-language search** — dex-number-based expansion, single-Pokémon filter to avoid tag-team contamination, PokéAPI backfill of 3.9k JP/KR card dex_ids
5. **TCGCSV migration** — Phase 1 archive backfill (~80 days dense history), Phase 2 daily sync becomes primary, pokemontcg.io demoted to cardmarket-only
6. **Storage cleanup** — dropped Cardmarket snapshots, recompressed 31-90d weekly→monthly, VACUUM FULL — reclaimed 323 MB
7. **Mascot loader system** — 4 PixelLab APNGs (idle/fly/pack/sleep), random pick per mount, applied to all major loading states; smooth Dragonite for hero
8. **News section** — Phase 1 markdown + view counter, Phase 2 in-DB + `/admin/news` editor, Phase 3 English + category tabs (Drops/Market/TCG/Center/Guide/News)
9. **Admin panel** — `/admin/news` + `/admin/users` (search, soft delete, role toggle, self-action guards), AdminGuard + AdminNav, edge middleware
10. **Affiliate + ads pipeline** — TCGplayer Impact params hardcoded, eBay Partner Network approved (campid pending), AdSense verified + under review
11. **AdSense compliance pass** — privacy policy updated to disclose AdSense, ads.txt added, `/contact` page created
12. **Anti-bot Phase 1** — honeypot + per-IP rate limit + disposable email blocklist on `/auth/signup`

---

## 12. External references / accounts

| Service | Purpose |
|---|---|
| Neon | Postgres database (Free tier, 512 MB) |
| Render | Backend host (Free tier) |
| Vercel | Frontend host (Free tier) |
| Cloudflare | DNS for pulllist.org |
| GitHub | Source + Actions cron |
| pokemontcg.io | Card catalog + Cardmarket prices |
| TCGCSV | Daily TCGplayer price archive (primary pricing source) |
| TCGdex | JP card catalog (CC-BY-NC) |
| Bulbapedia | JP rarity tables (CC-BY-SA-NC) |
| japon-collection.com | JP set logos (SwSh era) |
| PokéAPI | Multi-language Pokémon name index |
| eBay Developer | Browse API for live listings + price snapshots |
| Anthropic Console | Claude Haiku 4.5 (vision scanning) |
| impact.com | TCGplayer affiliate (approved, 3.5%) |
| eBay Partner Network | eBay affiliate (live, 1–4%, campaign 5339157076) |
| Google AdSense | Site verified (pub-9440218369165896), under review |
| PixelLab | Pixel-art mascots (MCP integrated) |

---

## 13. One-paragraph elevator pitch

PullList is a Pokémon TCG collector platform built for the global
audience — English, Japanese, and Korean catalogs in one place — with
daily-updated market data, per-variant collection tracking, cross-
language card search, and a Bulk/Chase tier split that surfaces moves
that actually matter. We charge nothing for the platform (ad-supported
via AdSense + TCGplayer/eBay affiliate). A future Pro tier
($5.99/mo via Lemon Squeezy) adds ad-free, alerts, deeper history, and
CSV import. The moat is the multilingual catalog + market data quality
the EN-first competitors don't bother with.
