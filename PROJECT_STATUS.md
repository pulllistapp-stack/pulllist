# PullList — Project Status

**Last meaningful update**: 2026-07-05

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
- **Level 3 auth** — 15-min access JWT (Bearer, localStorage) + 60-day opaque refresh token (httpOnly cookie, `SameSite=None; Secure; Partitioned`, sha256-hashed in DB). Rotated on every refresh call; reuse-of-revoked triggers full user-wide session nuke (theft signal). Endpoints: `/auth/{signup,login,google,refresh,logout,logout-all,sessions}` (signup / login / Google OAuth, rate-limited + honeypotted signup)
- **Admin role** (`users.is_admin`) + soft delete (`users.deleted_at`)
- DM Sans + JetBrains Mono fonts
- Light/dark theme via CSS variables, `next-themes`
- Site-wide footer (text wordmark), 4-card Contact page, Privacy/Terms/About

### 3.2 Catalog & data
- **43,000+ cards** (EN 21,250 + JA 21,837)
- **500+ sets** (EN 187 + JA 316 — including all JP promo eras JPP-XY/SwSh/SM/SV/S)
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
- **eBay sold Playwright scraper** hardened (`backend/scripts/scrape_ebay_sold.py`)
  after §11.33's five-issue push: slash-format card-number priority match
  (kills "170 HP" → card #170 false positives), quoted-number query
  wrapping + `_udlo=raw×0.30` URL price floor (defeats eBay's silent
  auto-relaxation that swaps datacenter-IP searches into "trending"
  results), universal `MIN_LISTINGS=2` with BGS 10 BL kept at 1, CGC
  Pristine/Perfect 10 classifier pattern (was leaking $17k slabs into
  `raw`), stale-snapshot pre-delete on Refresh, `_meta.last_scraped_at`
  in `/graded-prices` so the frontend can distinguish "0 recent sales"
  from "not tracked yet".
- **Snapshot retention** (`compress_snapshots.py`):
  - 0-7d: daily
  - 8-30d: weekly
  - 31-90d: monthly
  - 91-365d: monthly
  - 366d+: deleted
  - One-shot `storage_cleanup.py` reclaimed 323 MB (cardmarket drop + VACUUM FULL)

### 3.4 Collection management
- **CollectionItem** model (condition, grade, qty, acquired_at, notes, variant, purchase_price_usd, acquisition_type)
- **WishlistItem** model (priority, max_price_usd, notes, variant)
- **PortfolioSnapshot** model (daily valuation history per user)
- **Per-variant collection** — same card can be owned in multiple variants (e.g. normal + holofoil)
- **"+ I have this" modal** — variant (only when 2+ printings exist), condition, graded slab w/ service+grade, qty, acquired date, purchase price, source (pull/trade/purchase/gift/other), notes
- **Per-row expand panel** — ▼ Details pill on each vault card inline-shows acquired date / paid (with ±% ROI vs market) / source / notes; ✎ Edit button inside opens the per-row edit modal (variant, condition, grade, qty, all fields editable + Delete)
- Heart toggle for wishlist on every thumbnail
- Wishlist target price modal (priority, target $, notes, live "at target" hint)
- Portfolio page: stats grid, asset mix donut, growth chart (SVG area), Top 10 by value, full vault grouped by set
- **Variant chip** on Portfolio + Wishlist rows for non-default prints (holo, reverse, 1st ed, etc.)
- **Portfolio Manage mode** — checkbox bulk-select, sticky delete bar, type-DELETE confirmation for 2+ items
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
- Stats reflect actual catalog: **43,000+ cards** / **500+ sets** / **Daily price snapshots**
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
- `/admin/reports` — user-submitted card data-quality reports (Wrong price / Wrong image / Wrong name / Other); status tabs (Open/Resolved/Won't fix/All), inline resolution note, per-row Resolve/Won't fix/Re-open actions
- `/admin/visits` — self-hosted traffic dashboard: today/yesterday/7d views + unique-visitor counts (anon + signed-in), 7-day daily bar chart, country breakdown w/ flag emoji + CN/RU/KP/IR ShieldAlert surfacing, per-user table with 1d/7d/30d windows (views, last seen, last country)
- Self-action guards (admin can't demote or delete themself)
- Shared `<AdminNav>` strip (News / Users / Reports / Visits)
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

### 3.17 Master Sets (binder tracker) — shipped 2026-07-06/07
- **DB**: `master_sets` table (user_id + set_id UNIQUE, binder_size, display_mode, sort_mode, cover_image_url TEXT, share_token, completed_at)
- **API**: `/master-sets` — list / create / patch / delete / detail (binder view). Cover: PUT/DELETE. Share: POST/DELETE + public GET `/master-sets/public/{token}`. Reverse: `/master-sets/for-card/{card_id}`. Bulk-add: `POST /master-sets/{id}/spread/{n}/collect`.
- **Frontend** (`/portfolio/masters/*`, `/p/masters/[token]`): closed-cover → open-spread 3D binder with page-flip animation (framer-motion rotateY, 900ms cubic-bezier + midpoint content snapshot). Cover states: default mascot / user-uploaded photo / gold-completed. Physical grammar: diamond quilt (multiply + screen), 4-side zip-around, spine crease + vertical stitch on left edge, dashed stitch border, set-logo chip, sparkles on completion. Public URLs at `/p/masters/{token}` — read-only.
- **Completion**: backend auto-stamps `completed_at` on the detail read when base progress first hits 100% and flags `just_completed=true`. Client fires canvas-confetti one-shot + slide-in banner ("★ Master Complete ★") on that flag. Gold treatment persists thereafter (fly.png mascot, gold stitching, amber caption, sparkle diamonds).
- **Collect-this-spread**: yellow pill in header calls the bulk endpoint that walks the current spread's slots and adds any (card, variant) pair the user doesn't own. Toast confirms count; binder view reloads so newly-owned cards flip grayscale → colour.
- **Reverse link**: `InMyMasterSetsBadge` on card detail — shows the caller's master set for this card's set (progress bar + link), or a soft "Track this set" prompt if none.
- **Set-level reports** (in same push): `set_reports` table + `POST /sets/{id}/reports` + admin scope toggle at `/admin/reports` (Card vs Set).
- **Back-button hygiene**: filter/pagination/sort now use `router.replace` (not push) so hitting Back leaves the list page cleanly. Binder open/spread state persisted via `?open=1&spread=N` so Back from card detail restores the spread.
- **Legal**: `/legal` page with affiliate disclosure, CC/MIT attributions, DMCA takedown process, user-upload rights notice. Compact footer bar + inline Nintendo/TPC trademark disclaimer stays on every page.

---

## 4. Pricing & business model — current plan

```
PullList Free  $0 forever
  Catalog (43,000+ cards) · Collection tracker · Wishlist
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
13. **Portfolio polish pass** — variant chips for non-default prints, Manage mode w/ checkbox bulk-delete + type-DELETE confirm, full-options "+ I have this" modal (variant/condition/grade/qty/purchase price/source/notes) replacing the 1-click toggle, per-row ▼ Details expand panel surfacing the metadata inline with ±% ROI band + ✎ Edit modal for write access; `collection_items` gains `purchase_price_usd` + `acquisition_type` columns for ROI tracking
14. **Card data-quality reports** — "🚩 Report an issue" on every card detail page → 4-category modal (price/image/name/other) → `card_reports` table → `/admin/reports` triage UI with status tabs + inline resolution notes. Anonymous OK; signed-in submissions attributed to the user.
15. **Visit tracking (self-hosted analytics)** — `visit_logs` table + `<TrackVisit/>` client component + `/api/track-visit` route handler that lifts country/region/city from Vercel edge headers (no external geo API, no IPs stored). `/admin/visits` dashboard shows today's views/uniques, 7-day bar chart, country grid (with CN/RU/KP/IR flagging), and per-user table with last-seen country. Anonymous visitors get a localStorage UUID so unique counts cover non-signed-in traffic too. Skips `/admin/*` paths to avoid polluting numbers with triage browsing.
16. **JP rarity backfill (97.5% coverage)** — three-source sweep: Limitless EN-equivalent picker (`backfill_jp_rarity.py`) newly labelled 1,773 cards across SM/XY/CP recent imports; Bulbapedia sweep (`backfill_jp_rarity_bulbapedia.py`) with 32 expanded slugs (modern SV/M/S + vintage PMCG/E/PCG/VS/web) updated 8,234 rows for JP-native tier accuracy (RRR/AR/SAR/HR/UR labels Limitless EN-mapper collapsed); new `backfill_jpp_promo_rarity.py` blanket-filled 2,009 JPP-* cards as 'Promo'. Final state: 366 NULL / 14,362 JP cards = 97.5%. Original ROADMAP §10.5 plan (Playwright + pokemon-card.com) abandoned after probes confirmed the site indexes neither rarity nor vintage. 1,861 vintage image gap still open as §10.6.
17. **Level 3 auth (short access + rotating refresh)** — replaces the single 14-day JWT that iOS Safari ITP was wiping unpredictably. New `refresh_tokens` table (sha256 hash, per-device label, revoked_at). Access JWT drops to 15 min; refresh cookie carries 60 days, httpOnly + `SameSite=None; Secure; Partitioned` (CHIPS) so Chrome accepts it across Vercel↔Render. Frontend `authFetch` intercepts 401 → single-flight `/auth/refresh` → retry once → redirect on failure. Reuse-of-revoked triggers user-wide token nuke. Adds `/auth/logout` (server-side revoke), `/auth/logout-all` (kill every device), `/auth/sessions` (list live devices with "this device" marker) — the last one is Pro-tier selling material. Removes the fake "Stay logged in for 30 days" checkbox that was UI-only. Migration is additive-only (`migrate_add_refresh_tokens.py --dry-run`), old 14-day tokens keep working until they naturally expire.

18. **Master Sets binder tracker** (2026-07-06/07 push) — full set-completion feature. `master_sets` table with cover / share / completion columns. Closed cover → open 3D spread with framer-motion rotateY page flip (900ms cubic-bezier + midpoint content snapshot). Cover state stack: dark charcoal shell, diamond-quilted PU material (5px cycle multiply+screen), 4-side zip-around (`ZipperStrip` with vertical/horizontal orientations sharing a 3-layer tape+teeth template), left-edge spine (7% shadow band + 2% crease + vertical stitched crease at 7%), dashed border stitching (silver → gold on completion), semi-transparent set-logo chip bottom-right. User covers uploaded via canvas resize (`fileToResizedDataUrl`, target 700KB JPEG) stored as data: URL in `cover_image_url` TEXT column. Completion is auto-stamped by the detail endpoint on first 100% base hit; backend returns `just_completed=true` on that one response so the frontend fires a canvas-confetti burst + banner one-shot. Persistent gold treatment (fly.png mascot + gold stitches + sparkle diamonds + amber caption) sticks thereafter. Public read-only share via `?token=` on `/p/masters/{token}` — mint/copy/revoke modal in the detail page. Reverse "In your master set" badge on card detail via `GET /master-sets/for-card/{card_id}`. Bulk-add "＋ Collect this spread" pill in the binder header calls `POST /master-sets/{id}/spread/{n}/collect` — walks the current spread's slots and inserts CollectionItems for every unowned (card, variant). Toast confirms count; view reloads so newly-owned cards flip grayscale → colour instantly. URL-persisted state (`?open=1&spread=N`) so Back from card detail returns the user to the same spread instead of resetting to the closed cover.

19. **Set-level reports + admin scope toggle** — parallel to card reports: `set_reports` table + `POST /sets/{id}/reports` (4 categories: missing_cards/wrong_images/wrong_metadata/other), anonymous OK. `/admin/reports` grows a Card/Set scope toggle at the top; both scopes share the same row layout so triage doesn't require re-parsing.

20. **Back-button hygiene site-wide** — every filter tap, rarity toggle, sort change, page navigation, and region chip on `/cards` and `/sets/[id]` now uses `router.replace` (was `router.push`), so hitting Back after browsing exits the list page cleanly instead of unwinding 8 filter states.

21. **Layout + legal restructure** — Site max-width bumped 1280px → 1600px (`max-w-7xl` → `max-w-[100rem]`) across every page so grids fill wider monitors. Footer bottom bar compressed to a single-line "© 2026 PullList · Fan-built · Affiliate & attributions" with the Nintendo/TPC trademark disclaimer kept inline (etiquette). Full affiliate disclosure, CC/MIT attributions, and DMCA takedown process live on a new `/legal` page linked from footer + Company column. Master-set cover upload includes an ownership + `/legal` link warning.

22. **Neon compute optimization pass** (2026-07-13) — Neon Free-tier CU-hrs hit 103.23/100 this billing cycle after products + visit-tracking work. Four targeted cuts to bring us back under before deciding on Render Postgres / Supabase / Neon Launch migration: (a) `/admin/visits/top-referrers` — Python `defaultdict` bucketing rewritten as SQL `regexp_replace` + `GROUP BY domain`; formerly pulled every row in the window into memory just to hostname-normalize, now sends only top-N. (b) `SetSealedProducts` — 5-min `sessionStorage` cache keyed by set_id so hopping between `/sets/[id]` pages during a browse session stops re-hitting `/products/set/{id}/list`. (c) `/products` + `/products/{id}` + `/products/set/{id}/list` — `Cache-Control: public, s-maxage=300, stale-while-revalidate=600` so Vercel/Render edges serve cached responses for the daily-updated catalog. (d) `sync_tcgcsv_daily.py` — batch-load cards per group via `SELECT WHERE id IN (…)` instead of N `db.get()` round-trips (500k+ SELECTs → ~25 SELECTs/day), plus skip-if-unchanged guard on card UPDATEs (rounded 3-decimal compare on market/low/high/mid; dict-equal on `tcgplayer_prices` JSON) so bulk floors stop rewriting the same $0.05 rows every night. Adds `cards_unchanged` stat to daily sync summary so we can see the skip ratio.

23. **Neon → Render Postgres migration** (2026-07-13) — cut Neon free-tier CU-hr risk permanently. Provisioned Render Postgres Basic-256mb ($6/mo) + 5GB storage w/ autoscaling in the same Ohio region as the backend service — internal DNS `dpg-…-a` means <1ms round-trip vs the 5-15ms Neon inter-region hop. Built `backend/scripts/migrate_pg_to_pg.py` (SQLAlchemy `Base.metadata.create_all` + `sorted_tables` FK-ordered batch copy at 500 rows/txn, no `pg_dump` dependency) — copied 515,979 rows across 17 tables in ~11 minutes; a follow-up delta pass caught 194 `card_price_snapshots` rows that landed on Neon during the copy window. Post-copy trip on live cutover: SERIAL sequences on TARGET were still at 1 (rows carry explicit ids from source, so `nextval()` never advanced), causing every INSERT after the DATABASE_URL swap to `UniqueViolationError`. Fixed by enumerating every column with `pg_get_serial_sequence()` non-null and running `SELECT setval(seq, MAX(id)+1, false)` per table. The migration script now runs that step automatically as the last stage before verification. Total change: `DATABASE_URL` swap on the Render backend service (internal URL, no `?ssl=require`, keeps `+asyncpg` prefix); Neon left intact as read-only fallback for 24-48h then paused. Net effect: no more per-hour compute metering, ~5-15ms latency shaved off every DB round-trip, monthly bill drops from Neon's likely-$19 Launch tier to Render's flat $7.50 (instance + storage).

24. **Multi-Grade prices — Phase 2** (2026-07-13) — closes the loop between the Phase 1 groundwork (grade column, canonical vocab, `services.grade_classifier`, `GradedPricesGrid.tsx` UI shell) and live per-tier medians. `snapshot_ebay.collect_from_ebay` now returns a list instead of a dict — every kept eBay listing runs through `classify_grade(title)`, gets bucketed by grade tag, and each bucket with ≥2 listings emits its own snapshot row. One card → up to 11 rows per snapshot day, each carrying its own median/low/high/kept-count. Card headline `market_price_usd` backfill now sources from the raw bucket only, so graded slabs never leak into catalog prices. Backend `GET /cards/{card_id}/graded-prices` reads the last 90 days of `source='ebay'` snapshots, keeps the most recent row per grade tier, and returns `{psa10, psa9, cgc10, cgc9}` (nulls for empty tiers) — the exact shape `GradedPricesGrid` already fetches. Phase 2a (retroactive backfill of existing rows) is skipped because listing titles were never persisted; historical `grade='raw'` medians therefore include some slab contamination and will decay out as the new pipeline runs.

25. **Multi-Grade Phase 2d + 2e — dedicated PSA10 query + DOW rotation** (2026-07-13) — Phase 2c populated the grade column but every row landed as `raw` because eBay's Browse API returns raw listings for a bare "card name + number" query — slabs only surface when the query explicitly includes the grader token. Fixed by (d) adding a `disable_sanity_ceiling` param to `ebay_client.price_summary_with_trace` that also swaps the title-noise filter to `_TITLE_NOISE_FOR_GRADED` (grader tokens removed from the drop list), and (e) fanning `collect_from_ebay` out into one raw pass + one PSA 10 pass per card. Live verification on Umbreon ex 161 Prismatic (sv8pt5-161) returned raw median $1,500 (matches TCG ref $1,511) and PSA 10 median $7,949 (matches real market $7,200-$8,000). Phase 2e generalizes this to 4-tier via day-of-week rotation: Mon `PSA 10`, Tue `CGC 10`, Thu `PSA 9`, Fri `CGC 9`. Each grade tier gets a weekly refresh — slab prices are sticky enough that a weekly cadence per tier isn't a downgrade over daily. `snapshot_ebay --graded-tiers` CLI arg overrides the module-level `_GRADED_QUERY_SUFFIXES` default; the workflow computes the day's tier from `date -u +%u` and passes it in. Manual runs override via the `graded_tiers` workflow_dispatch input. eBay Growth Check (5k → 50k Browse quota) was denied 2026-06-29 with a generic template — this rotation is the practical ceiling within our current 5k/day cap.

26. **Neon → Render Postgres migration** (2026-07-13) — see §11.23 above. Live cutover was 13:00 UTC; after the first live INSERT threw `UniqueViolationError` because SERIAL sequences on TARGET were still at 1 (rows carry explicit ids from source, so `nextval()` never advanced), we walked every column with `pg_get_serial_sequence()` non-null and ran `SELECT setval(seq, MAX(id)+1, false)` per table. The migration script now runs that step automatically. Backend `DATABASE_URL` swap on Render + `?ssl=require` stripped for the internal DNS name; Neon left intact for 24-48h as read-only fallback.

27. **Set completion — Master + Full Set split** (2026-07-13) — the small completion card on /sets/[id] treated every card the same, collapsing a 219-card Master set's 130 base numbered cards with its 89 secret / SIR / hyper-rare tail into one progress number that lied about "the set." Backend `GET /collection/sets/{id}/completion` grew `full_set_total / full_set_owned / master_total / master_owned` fields. First heuristic (`number_int <= printed_total`) shipped, then fell over on `fpic-s2` (First Partner Illustration Series 2 declares `printed_total=9` but its cards number 46-54 as a cross-series continuous sequence, so every owned card was mis-classified as "not in the base run"). Fixed by ranking every card in the set by `number_int NULLS LAST` and treating the first `printed_total` as the base run — trivially handles the FPIC case (top 9 = the whole set) and normal secret-rare sets. Frontend widget became a header banner: Master completion ring (%), owned / total stats, Full Set (red) + Master (teal) horizontal progress bars, logged-out state teaches set size before the auth wall.

28. **Products expansion — sealed inventory + price history + series pages** (2026-07-13) — five-part push turning /products from a static catalog into a first-class sealed dashboard. (A) `/sets/[id]` splits into Cards | Sealed tabs with URL-persisted state; `SetSealedProducts` gains an `expanded` mode for the tab body with a proper empty state. (B) new `sealed_collection_items` + `sealed_wishlist_items` tables, `/sealed/collection` / `/sealed/wishlist` / `/sealed/state` endpoints, `ProductOwnButtons` client island on the detail page ("Mark as owned" + "Add to wishlist"), and `/portfolio/sealed` tab with owned / wishlist sections + header stats. (C) new `product_price_snapshots` table, `sync_products_daily.py` cron (08:15 UTC) that walks every group and snapshots the day's TCGCSV price feed, `GET /products/{id}/history` endpoint mirroring `/cards/{id}/history`, and `ProductPriceChart` hand-rolled SVG sparkline on the detail page (30d / 90d / 6M / 1Y range toggle, stat row w/ latest + % change + range hi/lo). (E) `batch_ingest_products.py` matches TCGCSV groups to our EN sets by name-token overlap + zero-padded era code (SV1 <-> SV01), lifting coverage from 7 sets / 320 SKUs to **39 sets / 963 SKUs** — every SV / SWSH era set now carries its sealed lineup. (G) new `/series` index + `/series/[slug]` landing pages backed by `GET /series` and `GET /series/{slug}` — one screen per era (Scarlet & Violet, Sword & Shield, ...) with every set + every sealed product across the era; TopNav grows a Series link and `/sets/[id]` "Series · X" label deep-links to the corresponding slug. Deferred: (D) deal alerts (needs email infra — Resend / SendGrid — save for post-launch), (F) UI/UX polish pass.

30. **eBay sold-listing pipeline via Playwright** (2026-07-13/14) — closes the loop that Multi-Grade Phase 2 opened: the tiles were populated by ACTIVE (asking) medians, but sellers routinely list slabs 10-30% above the clearing price. eBay's Marketplace Insights API (returns sold data cleanly) was declined 2026-06-29, and direct HTTP scraping returns 403 (the site's automated-request protection TLS handshake pattern). Solved by driving a real Chromium via Playwright + `playwright-stealth`: warm up on `ebay.com/` first (3.5s wait lets the the site's automated-request protection challenge cookie settle in the context), then navigate to `/sch/…?LH_Sold=1&LH_Complete=1`, then parse the new `li.s-card` DOM (title in `.s-card__title span`, price in `.s-card__price`). Retry once with a fresh context if the first attempt returns <30 s-card hits — the site's automated-request protection throttle responses are stateful and a new context usually clears them. `backend/scripts/scrape_ebay_sold.py` mirrors `snapshot_ebay`'s shape (chase-only card filter, per-card query = name + number + set + tier, `classify_grade()` bucket, per-tier median) and writes to `card_price_snapshots` with the new `source='ebay_sold'` (kept distinct from `source='ebay'` asking so the graded-prices endpoint can prefer sold). `GET /cards/{card_id}/graded-prices` now orders by `(snapshot_date DESC, source_priority ASC)` with `ebay_sold=0, ebay=1`, so sold wins same-day ties. Data-quality tuning after the first prod run: `MIN_LISTINGS_PER_GRADE 2→5` (n=3-4 buckets produced unstable medians), 10%/90% percentile trim (guarded by `TRIM_MIN_N=10`) to kill $174k Pikachu / $19.99 raw slip-throughs, strict card-number match (previously accepted any listing whose title had no `d/d` pattern — let "Pokemon PSA 10 Gem Mint Lot" pass Shining Charizard 107), and a card-name filter (first content word ≥3 chars, stopwords + `ex/gx/vmax/vstar` filtered, substring match not word-bound so `UmbreonEX` still passes). Per-card log surfaces `rej {number, name, grade}` so bad queries fail loudly. Two workflows on GitHub Actions: `.github/workflows/ebay-sold-scrape.yml` for the weekly per-tier rotation (Sun PSA 10 / Tue CGC 10 / Wed PSA 9 / Sat CGC 9 at 09:00 UTC), and `.github/workflows/ebay-sold-full-rotation.yml` for on-demand full sweeps that spawn all 4 tiers on separate runners simultaneously (matrix strategy — different IPs distribute the site's automated-request protection load, wall time compresses from ~3h sequential to ~2h parallel). Both wrap the Python call in `xvfb-run` because pure `headless=True` Chromium is fingerprinted by the site's automated-request protection; visible-mode Chromium under a virtual X server defeats the check. First overnight run (2026-07-14, 300/tier × 4 tiers, min-price $30, throttle 2s): 4/4 tiers succeeded in 1h50m wall time, 332 snapshots landed across 190 unique cards (PSA 10: 95 rows avg n=24, PSA 9: 149 rows avg n=18, CGC 10: 55 rows avg n=14, CGC 9: 33 rows avg n=9). 27.7% write rate on attempted queries — the rest fell below MIN_LISTINGS=5 or were throttled. 63 cards now have BOTH sold + asking data; CGC tier especially shows why sold matters (Umbreon CGC 10 sold $6,450 vs asking $2,747, Charizard CGC 10 sold $3,358 vs asking $9,500, etc.). Confirmed edge cases: vintage cards (Shining Charizard) have thin CGC populations so those tiles legitimately stay empty even after a full sweep — market reality, not a data bug. throttle response artifacts (query returns 0 s-card blocks in both retry attempts) show up as `n=0 (rej all 0)` in the log and are random; the next rotation usually clears them.

31. **eBay pipeline expansion — asking fallback, TAG/BGS tiers, user Refresh, repo public window** (2026-07-15) — three-part push on top of §29's sold-only pipeline, plus a strategic visibility flip. (A) Asking fallback pass. Sold data is thin for vintage CGC and modern TAG tiers — plenty of active listings exist on eBay but few clear the 5-sale MIN. Script now runs a second Playwright pass without `LH_Sold=1` when the sold pass returns n<MIN, writes as `source='ebay_asking'` (distinct key so nothing gets blended), and applies a RELAXED card-number filter for the fallback pass (sold=strict, asking=name+grade only — active listings don't always spell out "#107" but still map to the right card by name). URL also gains `_sacat=0` (all categories) so the URL shape matches what a real search-bar user produces, which meaningfully cut the throttle-response rate. (B) BGS + TAG grader support. `grade_classifier.py` gains `_BGS_RE` (already existed) plus `_TAG_RE` with the same word-boundary+immediate-digit shape as PSA/CGC — verified 7/7 on the "Tag Team" false-positive edge case. Canonical vocab grows to `bgs10/9.5/9` + `tag10/9.5/9`. Endpoint `ui_tiers` extends to 10 entries; frontend `TIER_META` gets indigo BGS + rose TAG accents. Every matrix workflow (weekly-sweep + full-rotation + refresh-one-card) gets the 3 new tiers added. Total tiles per card: **10**. (C) User-triggered Refresh button on card detail. `POST /cards/{card_id}/refresh-graded-prices` — signed-in only, 5-min per-card cooldown (during beta; bumps to 30 min post-launch), fires a `workflow_dispatch` API call to `ebay-sold-refresh-one-card.yml` with the card_id input. That workflow scrapes all 10 tiers for the one card sequentially (~10-15 min end-to-end, ~15 min GH Actions billing per click). Uses `GH_ACTIONS_TOKEN` env var on Render backend (PAT with `actions:write` on the repo). Endpoint returns 202/429/401/503 cleanly. `GradedPricesGrid.tsx` grows a Refresh pill next to the section header — sits subtle until ≤2 tiles have data, then promotes to solid green ("Refresh — get live data") so users don't miss the escape hatch on thin cards. Post-click state reads "Queued · Reload in ~3 min" so users know what to do. Empty tile copy replaces "No sold listings indexed yet" with the collaborative "Not tracked yet — hit Refresh above to check now." Data flow verified end-to-end: refresh Charizard SV3-125 lands 53 sold PSA 10 listings ($100 median) in the DB and the tile flips green after reload. Fix: `_flush` switched from `ON CONFLICT DO NOTHING` to `DO UPDATE` so a same-day rescrape overwrites stale morning data (was silently no-op'd, so Refresh felt broken). (D) Repo visibility flip to public for the beta backfill window. Private-repo GH Actions is 2000 min/mo free; the 10-tier matrix sweep + refresh clicks would run ~$50/mo overage. Public GitHub repos get unlimited free minutes. Defensive prep before flip: added `LICENSE` (all-rights-reserved, personal viewing OK, commercial forbidden), README top-of-file "not open source, see LICENSE" notice, and neutralized aggressive scraping terminology across the codebase (vendor names removed, "bypass" → "handle", "soft-block" → "throttle response", "fingerprint" → "TLS handshake pattern") so an abuse team googling the vendor doesn't find PullList's playbook. Plan: run 5 rounds of full-rotation matrix (limit 800 per tier × 10 tiers, min-price bumps 35→25 after Round 1, skip-if-recent-days=1 after Round 1) to fully cover EN $25+ = 2,757 cards, then flip back to private with a $0 spending limit on GH Actions so the meter can't overshoot. Round 1 mid-progress at time of writing: 651 snapshots written across ebay_sold (434) + ebay_asking (216) + 1 legacy ebay row, all 10 tiers producing rows. Full-rotation timeout bumped 200→350 min for rounds 2+ so each per-tier runner can chew through ~700 cards before the 6h GH job cap.

34. **eBay Round 5+6 + BGS/TAG recall lift + set-page consensus fix** (2026-07-18/19) — three chained improvements finishing the eBay-sold coverage push §11.33 opened. **(A) BGS/TAG recall lift** (Plans B+C+D combined). Round 4 exposed a sharp precision/recall gap on non-PSA graders: BGS 10 wrote 4.8% of processed cards, BGS 10 BL 4.9%, TAG 10 10.2% (vs PSA 10 at 37.5%). Auto-relaxation fired 2-3× more often on BGS/TAG queries because eBay's result-density heuristic treats "Card BGS 10 Beckett Black Label" as too narrow and swaps in trending Pokemon results. LO's ask: "even with some noise, catch the brand's cards" — recall > precision reversal for these tiers only, and grade purity must survive. **Plan B**: universal `MIN_LISTINGS=1` for every BGS/TAG grade (bgs10 / bgs10bl / bgs9.5 / bgs9 / tag10 / tag9.5 / tag9); PSA/CGC stay at MIN=2. Also bumped `max_attempts` 2→3 for BGS/TAG passes because those grade searches hit throttle responses more often, and one extra fresh-context retry usually clears them. Same knob unchanged on PSA/CGC. **Plan C**: Beckett synonym fallback. A meaningful fraction of eBay sellers list slabs as just "Beckett 10" (Beckett is BGS's parent brand). When the primary BGS sold pass returns below MIN, script now runs a second pass with `BGS` → `Beckett` swapped in the query. Downstream `_BECKETT_RE` in `grade_classifier.py` routes those titles into the same `bgs10 / bgs9.5 / bgs9` buckets, so the swap doesn't compromise grade purity. Only fires for BGS tiers; TAG has no equivalent synonym. Adds ~1 query per BGS card when needed, zero on PSA/CGC. **Plan D**: sort URL by ended-time ascending (`_sop=13`) for both sold and asking passes across all tiers. Round 4 diagnostic showed sm9-170 CGC 10 missed the May 7/8 $6,500 sales because Best Match sort pushed them behind lower-quality recent noise; sorted-by-newest guarantees the freshest sales land on page 1. New helpers `_max_attempts_for(grade)` and `_bgs_beckett_variant(query)` keep the tier routing readable. Round 5 (run 29652507216, 3h40m wall time — first sweep to finish under the 350min ceiling) ran the 5-tier matrix × 700 cards × `skip_if_recent_days=1` so Round 4-covered cards got skipped and Round 5 processed the next batch down the price ladder. Results: PSA 10 47.7% write rate (up from R4's 37.5% — the sort change alone lifted +10pp), CGC 10 36.3% (+7pp), **BGS 10 10.6% (+5.8pp = 2.2× lift)**, BGS 10 BL 4.1% (statistically unchanged — the market is genuinely thin at that grade), TAG 10 15.6% (+5.4pp = 1.5×). Beckett fallback fired 640× on BGS 10 and 678× on BGS 10 BL — most BGS queries needed it. Total: 800 snapshots written across 3,500 card-tier attempts (22.9% overall write rate, up from R4's 17.5%). **(B) Set-page consensus persistence fix**. LO caught: `/sets/[id]` tiles show raw TCG headline (e.g. $81.80 for Mega Chandelure ex) while `/cards/[id]` hero shows consensus $75.65 = (TCG + eBay median)/2. Same card, two numbers — reads as "the set page never updates." Root cause: three writers (unified Refresh endpoint, legacy Refresh endpoint, nightly TCGCSV sync) all persisted TCG-only into `Card.market_price_usd`, while `CardPriceHero` blended TCG + eBay client-side at render time. `CardThumb` on the set page reads the DB column directly and always trailed by the eBay component. Fixed by making every writer persist the consensus: `_refresh_raw_price_from_tcgcsv` fetches the latest raw eBay snapshot per card and blends before writing; `refresh_card_price` (the old Browse-API endpoint at /refresh-price) now writes the consensus it already computed for the response; `sync_tcgcsv_daily.py` batch-loads eBay medians per group via a single DISTINCT ON query and blends during the per-card update, with the change-detection guard updated to compare against the intended `new_market` so the "skip if nothing moved" optimization still fires. Also shipped one-shot `backfill_consensus_market_price.py` + `.github/workflows/backfill-consensus-market-price.yml` — single Postgres statement UPDATE ... FROM applying the same blend to every card that already has both signals. Run against prod (run 29666838256) reblended **5,673 of 6,063 eligible cards in 55 seconds**. Verified live: Mega Chandelure ex, Slowbro, and other Pitch Black cards now show the same consensus on both /sets/me5 and /cards/[id]. **(C) Round 6** — Option-1 continuation sweep (run 29669392217, 3h37m wall time). Same 5-tier matrix × 700 cards × `skip_if_recent_days=2` skipping every R4 + R5 hit and processing the next batch down the price ladder (rank ~1300-2000, mostly $25-80 chase). All B+C+D fixes active. Completed 100% (700/700 per tier) with **378 snapshots written total**: PSA 10 184 (26.3%), CGC 10 126 (18.0%), TAG 10 38 (5.4%), BGS 10 20 (2.9%), BGS 10 BL 10 (1.4%). Write rate dropped vs R5 as expected — the lower-value tail has thinner graded liquidity (fewer people submit a $30 card for grading, and eBay auto-relaxes those niche queries harder). Beckett-fallback measured **0/1318 hit rate** on R5 logs so it was disabled in `88a9d5a` before R6 fired; TAG got the same MIN=1 treatment on both runs. Cumulative across R4 + R5 + R6: **1,694 snapshots across ~2,000 EN cards** (~73% of the $25+ chase pool). **(D) Follow-up polish shipped during R6's wall time**. Diagnostic surfaced Beckett recall at 0.0% and prompted the fallback removal (`88a9d5a`). GradedPricesGrid folded the sub-10 tiles behind a "Show lower grades" toggle so the primary row (PSA 10 / CGC 10 / BGS 10 / BGS 10 BL / TAG 10) becomes a clean 5-across grid instead of a straggly 4-4-3 wrap. Pre-fix cleanup script `cleanup_pre_fix_graded_snapshots.py` (dry-runnable workflow) plus a partial index `ix_snapshot_ebay_raw_card_time` on `card_price_snapshots(card_id, snapshot_at DESC)` filtered to `source='ebay' AND grade='raw' AND market_price_usd IS NOT NULL` — feeds the consensus DISTINCT ON lookup used by nightly sync + Refresh + backfill without falling back to a full scan as the table grows. New `/trending/grading` page ranks cards by tier-price ÷ raw multiplier (PSA 10 default; CGC 10 / BGS 10 / BGS 10 BL / TAG 10 chips), Sold-only toggle on by default so anchor-listing pollution ($999,999 vintage-seller placeholders) doesn't spike the top; 300× multiplier ceiling gates the last of the extreme outliers.

    **Repo visibility close** — Post-R6, the beta backfill window closes: repo flips back private + GH Actions spending cap set to $0 so further per-card coverage happens through the user Refresh button (which shares the same B+C+D pipeline). Further sweeps would show diminishing returns (R4 37.5% → R5 47.7% → R6 26.3% on PSA 10 as we drill deeper into the $25-80 tail).

33. **eBay sold scraper — five-issue hardening + Round 4 sweep** (2026-07-16/17) — a full day's diagnostic dive triggered by LO reporting the sm9-170 Latias & Latios SIR PSA 10 tile stuck at $1,169 (real market $10-20k). Uncovered five distinct issues that were compounding to silently corrupt or empty most graded tiles for high-value cards: **(1) Card-number false-positive** — the previous number matcher accepted any listing whose title mentioned the digit "170", so #116/181 Team Up base prints (dirt-cheap) and any card with "170 HP" printed in the title (Latias & Latios GX has 170 HP) leaked into the sm9-170 result set. Fixed with a two-layer matcher: Layer 1 requires the number to appear inside a `NN/TTT` slash-format pair when the title contains any slash-format pair; Layer 2 falls back to a word-bounded bare-number match when no slash pair exists (keeps promo listings that never spell out a card number). **(2) eBay silently auto-relaxes queries on datacenter IPs**. Local Playwright test on the same query returned 53 clean PSA 10 matches; GitHub Actions runner IP returned 120 parsed listings but 118 got rejected by the number filter because eBay had silently substituted our specific query with a broader "trending Pokemon" result set (Booster Bundles, Chinese Latios cards, generic "New Listing" ads). Even wrapping the card number in quotes (`"170"`) didn't help — eBay ignored the quotes from datacenter IPs. Fixed by injecting `&_udlo=raw×0.30` into the search URL: eBay's minimum-price parameter is honored regardless of the query relaxation, so a `raw*0.3` floor (e.g. $1470 for a $4900 raw card) kills 95%+ of the Booster Bundle / wrong-set noise upstream. Verified live: sm9-170 PSA 10 pass went from 0 accepted → 6 clean matches ($6,591-$18,000 range, median $15,750). **(3) MIN_LISTINGS=5 threshold was throwing away real data on thin-market tiers**. BGS 10 Black Label, TAG 10, and vintage CGC populations are inherently thin — Pop reports for most SIR Black Labels are 3-10 globally, so 90-day sold counts of 1-4 are typical. Universal `MIN_LISTINGS=2` (BGS 10 BL kept at 1) with the price floor doing the noise-defense job upstream. **(4) CGC PRISTINE 10 misclassified as raw**. CGC's premium perfect-10 designation puts "PRISTINE" between the grader token and the digit (`CGC PRISTINE 10`), so `_CGC_RE = \\bCGC\\s*(\\d)` didn't match and the classifier fell through to `raw`. That silently dropped $17,577 CGC Pristine 10 sold listings from the CGC 10 tile. Added dedicated `_CGC_PRISTINE_RE` matching "CGC (GEM MINT)? PRISTINE 10" and "CGC PERFECT 10", checked before the general CGC regex, bucketed as `cgc10`. **(5) Stale contaminated snapshots weren't being cleared on Refresh**. `_flush` used `ON CONFLICT DO NOTHING` on the initial deploy, so if a fresh scrape wrote zero rows for a tier (correctly rejecting all false positives), the old contaminated Jul-13 snapshot stayed indefinitely. Switched to `ON CONFLICT DO UPDATE` for same-day rescrapes AND added a pre-scrape `DELETE FROM card_price_snapshots WHERE source IN ('ebay_sold','ebay_asking','ebay') AND snapshot_at < now() - 15 min` step to the refresh endpoint so contaminated data disappears immediately when the user hits Refresh even if the fresh scrape lands zero clean matches. Backend also gained a `_meta.last_scraped_at` field on `/cards/{id}/graded-prices` (max snapshot_date across ANY ebay row for the card, cheap index-only query) so the frontend can distinguish "no PSA 10 sold in the last 90 days" (real signal for scraped-recently cards) from "not tracked yet — hit Refresh above" (call-to-action for first-time visitors). Also added AUTO-RELAXED banner detection in the scraper log (fires when eBay's "No exact matches found" / "Results matching fewer words" text appears) plus reject-sample dumping when rejection rate exceeds 80% — future scraper debugging doesn't require a Playwright dive to see what titles eBay returned. **Round 4 sweep** (5-tier matrix × 700 cards, run 29540198480, 22:40 UTC to 04:30 UTC 07-17) cancelled at the 350min timeout with 570-618 cards processed per tier and 516 total snapshots written (Round 3 write rate on the old code: 12% for PSA 10 baseline; Round 4 hit 37.5% PSA 10, 29.1% CGC 10, 10.2% TAG 10 — 3× improvement). Sample verification: Umbreon sv8pt5-161 SIR now shows 10/11 tiers filled, Base Charizard base1-4 shows 10/11 with BGS 10 BL sold at $7,050 (Pristine 10 fix working), Rayquaza-esque swsh7-215 shows 9/11 with BGS 10 BL sold at $26,200. Sub-workstream: added Triple Whammy Tin 3-pack (Tyranitar/Darkrai/Slaking) to both sv09 and sv10 sealed tabs as a cross-set mirror (TCGCSV files them under "Miscellaneous Cards & Products" so per-set ingest was missing them) plus a synthetic `p-me30-etb-pkc` row for the 30th Celebration Pokemon Center ETB (identical art to the regular ETB, no TCGCSV SKU exists).

35. **Graded slab valuation across the vault** (2026-07-20) — the vault always valued items at raw market even when the row was flagged `is_graded` with a specific slab grade — a Charizard PSA 10 that clears at $4,800 showed up in the header at raw's $8, and the growth chart tracked raw drift instead of tier drift. Fixed by routing every valuation surface through `app/services/graded_pricing.py`: `user_grade_to_key(grade_str)` maps "PSA 10" / "BGS 9.5" / "CGC 10 Pristine" / "BGS 10 Black Label" / "TAG 10" to the canonical `card_price_snapshots.grade` key (11 tracked tiers matching `/graded-prices` output; PSA 8 / CGC 9.5 / Ace / SGC intentionally return None so we fall back to raw instead of pretending to have data). `resolve_graded_prices(db, keys)` bulk-loads the latest snapshot per (card_id, tier) with the same source-priority ladder as the tile endpoint (`ebay_sold > ebay_asking > ebay`, latest date first). `effective_price(...)` returns `(price, "graded"|"raw")` for one item — graded wins when a snapshot exists, raw is the graceful fallback. Wired into `list_my_items`, `set_completion`, `my_summary`, `export_collection_csv`, and `scripts/snapshot_portfolios.py` so header total, per-row market, per-set completion value, CSV, and the daily growth cron all agree; the summary/list rows also carry an optional `price_source` field for future UI badges. Frontend gets a shared `GradedTierPreview` component (used by both CardAddModal and CollectionItemEditModal) — flipping Graded on triggers a single `/cards/{id}/graded-prices` fetch cached across service/grade changes, and the panel shows the live tier median (amber card + link to card page's Refresh button when the tier has no data yet). ROI hint math'd against the tier price so a $500 buy on a PSA 10 that clears $4,800 reads +$4,300, not raw's misleading -$492. TAG added to `GRADE_SERVICES` on both modals (was PSA/BGS/CGC/SGC/Ace only). Grade string mapping shared via `frontend/lib/gradedTier.ts` so the frontend classifier stays in lockstep with the backend classifier.

36. **KR promo catalog import from namu.wiki** (2026-07-22) — before this push the DB carried a single KR promo set (`ko-c-5f2269d335`, 25주년 프로모팩 2021); every other KR promo card (base era through MEGA) had no catalog entry, so a KR collector had no way to add a "루기아 001 PROMO" or "치코리타 M-P" to their vault. Scraped `namu.wiki/w/포켓몬 카드 게임/한국 프로모 카드 일람` with Playwright (React SPA, so `domcontentloaded` + 5s hydration + 10× scroll-to-bottom), parsed the 7 era tables (초대 / BW / XY / SM / 소드실드 / SV / MEGA — ADV, DP/PT, 기타 sections are empty on namu today), and upserted **7 new sets + 748 new cards**. Option-B `ko-p-{era}` id convention (`ko-p-base` / `ko-p-bw` / `ko-p-xy` / `ko-p-sm` / `ko-p-ss` / `ko-p-sv` / `ko-p-mega`), one bucket per H2 era matching how JP promos are already grouped (`set.py::set_type` docstring — PROMO_NEW year buckets). Era classification is by the promo-code suffix on the "번호" cell (`/BW`, `/XY-P`, `/SM-P`, `/S-P`, `/SV-P`, `/M-P`, ` PROMO`) rather than DOM order, so the parser stays right if namu reshuffles headings. Card numbers preserve the numeric prefix (`ko-p-bw-001` from `001/BW`), and the one row with no leading number (`SV-P 파라다이스 리조트`) gets a synthetic `p001` sentinel. **Rowspan is heavy on this page** — namu collapses cards that share an acquisition event into a single rowspanned "획득 경로" cell (SV era's `스타터 세트 ex 동봉 프로모팩` covers a dozen rows), and a naive `<tr>.cells` read leaves the later rows in the group missing the number+name columns. Fixed with a grid-fill algorithm that walks each cell's `rowspan`/`colspan` and writes to every covered (row, col) so every logical row lands as a full triple; SV table alone went from 64 raw rows to 26 unique cards after dedupe-by-(number, name). Raw counts by era: base 22 · bw 72 · xy 191 · sm 196 · ss 191 · sv 26 · mega 50 = 748. **Missing (13 SS rows)**: `009/S-P` through `020/S-P` + `182/S-P` have namu structure quirks (nested rowspan across both number and name columns for a "reserved but not yet assigned" batch) that the grid-fill couldn't reach cleanly — logged and skipped rather than fabricated. LO can hand-fill from source when needed; those specific numbers are commonly empty on namu's own current draft. **No images** — the "일람" listing page has zero inline card thumbnails; images live only on individual card articles. Catalog imports without image URLs; a follow-up pass can source from tcgdex KR / pokemon.com KR / per-card namu article scrape. Script is idempotent (upsert by id, updates over inserts) and offers `--from-html <path>` for offline re-runs against a saved dump so LO doesn't burn another Playwright session for parser iterations. Rarity defaults to "Promo" on every row so trending/completion queries pick these up under the promo bucket instead of the "Unknown" tail.

32. **JP catalog price coverage — 15k cards from "$?" to live** (2026-07-16) — TCGCSV's Pokemon Japan category (id 85) carries prices for ~448 groups but our JP catalog cards had `tcgplayer_product_id IS NULL` on 15,611 of 15,611 rows (100% blank) so the daily sync couldn't touch them. First attempt at a name-based join returned **11 matches out of 15,611** — root cause: our JP catalog stores JP names (`ストライク`) while TCGCSV's JP category stores EN names (`Scyther`), so string match is worse than random. Fixed by switching to number-based matching in `backfill_jp_card_tcgcsv_ids.py`: card number is language-invariant and unique within a printed set, so `number_int` on our side joins cleanly against TCGCSV's `extendedData.Number` (parsed with `_LEADING_INT_RE` to strip `NNN/YYY` and `NNa` variants). Match rate jumped to **15,408/15,611 (98.7%)** across **222 sets** — remaining 116 sets don't exist on TCGCSV at all (unreleased/early/sub-sets). Second failure: per-row `db.commit()` on 15k UPDATEs blew past the 45-min GH Actions timeout mid-run; refactored to per-SET batch commit (30-80 rows/set) — ~200x faster and preserves partial-recovery semantics if a run gets cancelled. Also patched `sync_tcgcsv_daily.py` to loop **both** category 3 (EN) and category 85 (JP) in one sync run (product IDs don't collide between categories so single `product_to_card` map still works). One-shot workflow `.github/workflows/backfill-jp-prices.yml` runs Phase 2 (backfill tcg_pid) then Phase 3 (first sync). Final numbers: Phase 2 cards_written=3,873 + cards_already=11,614 = 15,487 with tcg_pid; Phase 3 cards_refreshed=20,254 + snapshots_inserted=25,234 + group_errors=0. Verified live: SVHK 53/53 pid + 36 with price, S12a 100/100 sample + 100 with price, S8a top price $775 (Mew UR), S6a top $255 (Eevee Heroes Sylveon). Nightly TCGCSV sync now maintains both languages automatically.

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
