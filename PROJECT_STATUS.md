# PullList — Project Status

**Last meaningful update**: 2026-06-15

Authoritative reference for what's been built, what's in progress, what's
planned, and the architectural decisions behind it. Maintained as a flat
markdown so any future session (LO, ENI, or a fresh collaborator) can land
on the project and understand the state in ~10 minutes.

---

## 1. What this is

PullList is a Pokémon TCG **collector platform** (positioning: not a Pokefy
alternative). Free site for catalog/tracker/charts; Pro tier (not yet live)
for restock alerts + power features. Future revenue mix: TCGplayer affiliate
commission + paid subscriptions.

- **Production**: https://pulllist.org
- **Repo**: `pulllistapp-stack/pulllist` (private)
- **Stage**: friends-beta
- **Audience target**: serious Pokémon TCG collectors (1k → 10k → 100k users)

---

## 2. Strategic decisions (locked in via /grill-me)

| # | Decision | Why |
|---|---|---|
| Q1 | Drops main = **store-level restock prediction** | Pokefy doesn't do this — unclaimed niche |
| Q2 | User target = **C: 50-500 paid subscribers** | Realistic indie SaaS scale |
| Q3 | Free/paid cut = **feature cut** (not quantity/time) | Clean, no nickel-and-dime |
| Q4 | Pro pricing = **$5.99/mo or $59/year** | Pokefy is $8 alert-only; we undercut with platform |
| Q5 | Payment infra = **LemonSqueezy** | Merchant of Record handles tax; indie SaaS standard |
| - | Positioning = **PullList = collector platform, NOT Pokefy alternative** | Different category; coexist with Pokefy |
| - | Mobile = **PWA → Google Play $25 → Apple $99/yr** | Phased; $0 to start |
| - | Card scan = **Claude Vision API** | Simple, accurate, ~$0.003/scan |
| - | Capability honest: ~6-12 months sustained to reach Pokefy parity | We have TargetBot anti-bot expertise to draw on |

---

## 3. Built — current state

### 3.1 Foundation
- Next.js 16 (App Router, React 19) frontend → Vercel
- FastAPI + SQLAlchemy 2.0 async + asyncpg backend → Render
- Neon Postgres
- JWT auth (signup / login / me)
- DM Sans + JetBrains Mono fonts
- Light/dark theme via CSS variables (`--bg`, `--text-primary`, etc.) — `next-themes`
- Site-wide footer with mascot, marketplace links, systems-operational pill

### 3.2 Catalog & data
- **12,000+ cards** seeded from pokemontcg.io
- **29 sets** including Mega Evolution era (me2 Phantasmal Flames, me3 Perfect Order, me4 Chaos Rising)
- Card detail page: hero with 3D-tilt + filled-star sparkle hover, price chart, secondary prices, live listings, breadcrumb, neighbors
- Set detail page: hero with logo + completion, sidebar filter (set-scoped rarity options), card grid
- Cards browse with sidebar filter (FilterSidebar): rarity / supertype / energy / subtype / set / artist / HP / price / condition / owned

### 3.3 Pricing pipeline
- **eBay Browse API** (live + daily snapshots)
- **pokemontcg.io daily sync** for TCGplayer + Cardmarket prices
- **Portfolio daily valuation snapshots** (per-user roll-up)
- **3 cron workflows** in GitHub Actions:
  - `daily-ebay-snapshot.yml` (03:00 UTC, 90min timeout)
  - `daily-tcgplayer-sync.yml` (04:00 UTC, 90min timeout)
  - `daily-portfolio-snapshot.yml` (05:00 UTC, 30min timeout)
- **3-layer eBay price sanity filtering** (debugging took 4 rounds):
  - Title noise (PSA grades, sealed product, sleeves, etc.)
  - Min 3 listings before recording (avoid single-outlier medians)
  - Rarity-based absolute floor (SIR ≥ $5, Mega Hyper ≥ $10)
  - TCG-reference-relative band (0.30x to 5.0x of TCGplayer market)
  - Card-number-in-title gate for chase rarities (SIR/IR/Hyper/Rainbow/Mega Hyper)
  - Rarity disambiguator appended to query (SIR / IR / Hyper Rare etc.)

### 3.4 Collection management
- **CollectionItem** model (condition, grade, qty, acquired_at, notes)
- **WishlistItem** model (priority 1-5, max_price_usd, notes)
- **PortfolioSnapshot** model (daily valuation history)
- One-tap "I have this" toggle on every card
- Heart toggle on every card thumbnail for wishlist
- Wishlist target price modal (priority stars + target $ + notes + live "at target" hint)
- Portfolio page: stats grid, asset mix donut, growth chart (SVG area), full vault grouped by set
- Trending page: Top 3 podium (gold/silver/bronze badges), mover rows with sparklines, period+source+direction filters, $1/$5/$10/$50 price floor

### 3.5 Rarity color system
- `lib/rarity.ts` — single source of truth for tier classification
- 13 tiers (common / uncommon / rare / holo / ultra / illustration / sir / mega / hyper / shiny / secret / promo / ace / other)
- Each tier has inactive + active styling
- Used by FilterSidebar chips, CardThumb labels, Trending rows, card detail header, scan results

### 3.6 Mobile / PWA
- `public/manifest.json` + `sw.js` + `PWARegister` client
- Add-to-home-screen on iOS Safari / Android Chrome
- Theme-color metadata for both modes
- Apple touch icon
- **Card scanning** (`/scan` page):
  - Mobile-only camera (`md:hidden`); desktop shows QR code fallback
  - Full-screen camera with Pokémon card aspect ratio targeting overlay
  - Flashlight toggle (when supported — Chrome Android yes, Safari iOS no)
  - Claude Haiku 4.5 vision → JSON identification
  - 3-tier DB fuzzy match (name+number+set → name+number → name only)
  - Top 5 candidates with rarity chip + price + one-tap Add
- **ScanFAB** — floating yellow action button bottom-right, mobile-only, hidden on `/scan`, `/login`, `/signup`, `/cards/*` pages

### 3.7 Homepage & marketing
- Auth-aware HeroCTA (logged-out: signup; logged-in: portfolio + scan)
- Trending strip (top 4 movers from /cards/trending)
- Latest sets section
- Feature pillars (Catalog / Live prices / History)
- Final CTA with mascot sparkles
- Atmospheric glows behind cards

### 3.8 Portfolio sharing (just shipped)
- Non-enumerable share_token URL: `/p/[24-char-base64url]`
- Opt-in public mode (default private)
- Per-section toggles: value / growth / wishlist / all_cards
- Token rotation (invalidates old URL)
- ShareModal on `/portfolio` with copy + rotate
- Public viewer (`/p/[token]`) shows mascot avatar + display name + bio + stats + asset mix + top 20 cards + set completion + optional growth/wishlist/full grid
- "Create your own" CTA at bottom for viral pull
- Open Graph metadata for link previews (image auto-generation = next sprint)

### 3.9 Affiliate / business prep
- TCGplayer affiliate application submitted via impact.com (review 1-2 weeks)
- impact.com site verification meta tag in `<head>`
- "Buy on TCGplayer" buttons throughout card detail (affiliate link slot ready)
- Anthropic API key live (Claude Haiku 4.5 for scanning, ~$5 credit)

### 3.10 Auxiliary projects
- **TargetBot** (separate folder `~/Desktop/TargetBot/`) — Patchright stealth bot for Target.com restock + auto-buy. Validated with real purchases. Domain-knowledge source for anti-bot work in future PullList alert pipeline.

---

## 4. Pricing & business model — current plan

```
PullList Free  $0 forever
  Catalog (12,000+ cards) · Collection tracker · Wishlist
  Portfolio + growth chart · Trending · Price history (7d/30d/90d/1y)
  Card scanning (5/day rate-limit, not enforced yet)
  Public portfolio sharing

PullList Pro  $5.99/mo  or  $59/year  (NOT LIVE YET)
  Best Buy / Costco / Microcenter / GameStop / DG / Pop Shelf
    in-store predictive restock alerts (Discord webhook + Email)
  Wishlist target-price alerts (Discord + Email)
  Daily portfolio digest email
  Unlimited card scanning
  CSV / Excel export
  Custom price alerts ("Chaos Rising SIR drops 15%")
```

Affiliate income: TCGplayer 3.5-4.5% commission on referred sales (passive).

---

## 5. Planned — roadmap

### Sprint 1 (current — partial)
- [x] PWA conversion
- [x] Card scanning V1
- [x] Portfolio sharing V1
- [ ] OG image auto-generation (`@vercel/og`) for share link previews
- [ ] Best Buy in-store predictive monitor V1 (single retailer, US only)
- [ ] Discord webhook + Email alert delivery
- [ ] Wishlist target-price alert dispatch (uses existing target field)
- [ ] Daily portfolio digest email
- [ ] CSV export endpoint + button

### Sprint 2
- [ ] LemonSqueezy integration (Subscription model + webhooks)
- [ ] Pro tier gating middleware
- [ ] `/pricing` marketing page
- [ ] Scan daily rate-limit enforcement (5/day free, unlimited Pro)
- [ ] User Settings page (notification prefs, ZIP, alert channels)

### Sprint 3+
- [ ] Costco / Microcenter / GameStop monitors (one per ~month)
- [ ] Walmart "Potential droplet" early-info detection (catalog entry monitoring)
- [ ] Expo (React Native) build for Google Play Store ($25 one-time)
- [ ] Trade calculator
- [ ] Wishlist sharing (separate token, different from portfolio token)
- [ ] Friend connections / collection comparison

### Future / not committed
- [ ] Apple App Store ($99/yr) — gate behind ~$500/mo MRR
- [ ] Auto-buy integration with linked retailer accounts (legally gray)
- [ ] Multi-region (CA / UK / EU / JP)
- [ ] Other TCGs (Magic, One Piece, Lorcana)
- [ ] PSA / BGS graded-slab specific tracking
- [ ] User-submitted price corrections (crowdsourcing)
- [ ] Tournament event tracking / deck builder integration

---

## 6. Known quirks / non-bugs

| Issue | Why it's not a bug | Workaround |
|---|---|---|
| New Mega Evolution sets show no TCGplayer prices | pokemontcg.io has 1-2 week lag for new sets; everybody else (including Pokefy) faces the same upstream constraint | eBay fills the gap; we have rarity-floor sanity guards |
| Trending page shows nothing for ~24h after deploy | Need 2+ snapshots of same (card, source, variant) for delta calculation | Wait one day after cron starts |
| Render free-tier cold start can take 30-50s | Backend free tier behavior; first request after idle is slow | Workflow timeouts set to 90min; user-facing pages tolerate via SSR |
| GitHub Actions scheduled crons sometimes need manual first-trigger | GitHub Actions can lag on new workflow schedule recognition | One manual `Run workflow` click confirms they're alive |
| Safari iOS doesn't expose camera torch | Browser-level limitation; not our code | Torch toggle silently hidden when unsupported |
| TCGplayer direct API is closed to new applicants | Post-eBay acquisition policy | We use pokemontcg.io (their official partner) for legal price data |
| eBay daily quota (5,000/day on free tier) | API limit | snapshot script uses `--max-calls 4500` with throttle; if hit, snapshot continues next day |

---

## 7. Tech stack reference

| Layer | Stack |
|---|---|
| Frontend framework | Next.js 16 (App Router), React 19 |
| Styling | Tailwind CSS 3, lucide-react icons, next-themes |
| Charts | Custom SVG (no library) |
| Backend framework | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 async |
| Database | Neon Postgres (production), SQLite (local dev) |
| HTTP client | httpx (backend), native fetch (frontend) |
| Auth | JWT (python-jose) + bcrypt password hashing |
| LLM | Claude Haiku 4.5 (Vision for card scan) via `anthropic` SDK |
| Cron / scheduling | GitHub Actions (free tier, ~660 of 2000 min/month used) |
| Deploy: frontend | Vercel (free tier) |
| Deploy: backend | Render (free tier — paid Pro when traffic justifies) |
| External APIs | pokemontcg.io (free), eBay Browse API (free 5k/day), Anthropic API ($5 credit) |
| PWA | Manual manifest + service worker (no `next-pwa` plugin) |
| Bot framework (TargetBot project) | Patchright (stealth Playwright fork) |

---

## 8. Environment variables

**Backend (Render)**:
- `DATABASE_URL` — Neon Postgres connection string
- `EBAY_APP_ID`, `EBAY_CERT_ID` — eBay Browse API credentials
- `EBAY_ENV=production`
- `ANTHROPIC_API_KEY` — Claude API key (for scanning)
- `POKEMONTCG_API_KEY` — optional, bumps rate limit from 1k/h to 20k/d
- `JWT_SECRET` — symmetric key
- `CORS_ORIGINS` — comma-separated allowed origins

**Frontend (Vercel)**:
- `NEXT_PUBLIC_API_BASE` — backend URL (e.g. `https://pulllist-api.onrender.com/api/v1`)

**Local dev (`.env` — gitignored)**:
- All of above; also `LOG_LEVEL=DEBUG`

---

## 9. Key file structure

```
pulllist/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── collection.py        # /me/collection + /portfolio/history
│   │   │   ├── filters.py           # /cards/filters/options (set-scoped)
│   │   │   ├── routes.py            # /cards/* + /trending + /live-listings
│   │   │   ├── scan.py              # /cards/scan (Claude Vision)
│   │   │   ├── sharing.py           # /p/{token} + /me/sharing
│   │   │   └── wishlist.py          # /wishlist/*
│   │   ├── models/                  # Card, Set, User, CollectionItem,
│   │   │                            # WishlistItem, CardPriceSnapshot,
│   │   │                            # PortfolioSnapshot
│   │   ├── services/
│   │   │   └── ebay_client.py       # Browse API wrapper + sanity filters
│   │   ├── schemas/
│   │   ├── main.py
│   │   └── database.py
│   ├── scripts/
│   │   ├── seed_sets.py             # one-time + --refresh
│   │   ├── snapshot_ebay.py         # daily eBay cron
│   │   ├── sync_tcgplayer_prices.py # daily TCG cron (via pokemontcg.io)
│   │   └── snapshot_portfolios.py   # daily portfolio cron
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── cards/
│   │   │   └── [id]/page.tsx
│   │   ├── sets/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── trending/page.tsx
│   │   ├── portfolio/page.tsx
│   │   ├── wishlist/page.tsx
│   │   ├── scan/page.tsx
│   │   ├── p/[token]/page.tsx       # public portfolio viewer
│   │   ├── page.tsx                 # home
│   │   ├── layout.tsx               # providers, PWA, theme
│   │   └── globals.css
│   ├── components/
│   │   ├── card/
│   │   │   ├── PullListCardDetail.tsx
│   │   │   └── LiveListings.tsx
│   │   ├── portfolio/
│   │   │   └── ShareModal.tsx
│   │   ├── scan/
│   │   │   └── CardScanner.tsx
│   │   ├── AuthProvider.tsx
│   │   ├── CollectionProvider.tsx
│   │   ├── WishlistProvider.tsx
│   │   ├── FilterSidebar.tsx
│   │   ├── CardThumb.tsx
│   │   ├── PortfolioGrowthChart.tsx
│   │   ├── AssetMixDonut.tsx
│   │   ├── RarityChip.tsx
│   │   ├── ScanFAB.tsx
│   │   ├── PWARegister.tsx
│   │   ├── Footer.tsx               # hidden on /scan
│   │   └── TopNav.tsx
│   ├── lib/
│   │   ├── api.ts                   # public + cached fetch helpers
│   │   ├── auth.ts                  # authed fetch + user/collection/wishlist
│   │   ├── rarity.ts                # tier classification + color maps
│   │   └── utils.ts
│   ├── public/
│   │   ├── pullist-mascot.png
│   │   ├── manifest.json
│   │   └── sw.js
│   ├── next.config.mjs              # remotePatterns: pokemontcg.io, ebayimg.com
│   └── package.json
├── .github/
│   └── workflows/
│       ├── daily-ebay-snapshot.yml      # 03:00 UTC, 90min
│       ├── daily-tcgplayer-sync.yml     # 04:00 UTC, 90min
│       └── daily-portfolio-snapshot.yml # 05:00 UTC, 30min
└── PROJECT_STATUS.md                # this file
```

---

## 10. External references / accounts

| Service | Purpose |
|---|---|
| Neon | Postgres database |
| Render | Backend host |
| Vercel | Frontend host |
| Cloudflare | DNS for pulllist.org |
| GitHub | Source + Actions |
| pokemontcg.io | Card catalog + TCGplayer/Cardmarket prices |
| eBay Developer | Browse API for live listings + price snapshots |
| Anthropic Console | Claude API for vision scanning |
| impact.com | TCGplayer affiliate program (pending review) |

---

## 11. The grill-me decisions in one paragraph

We are **NOT trying to be Pokefy**. Pokefy is a $8/mo Discord-based alert
service with multi-region multi-retailer coverage built up over years.
PullList is a **collector platform** — alerts are one feature among many,
not the product. We compete in a different category: collection tracking +
portfolio + wishlist + price history + scanning + sharing, with restock
alerts as a Pro-tier hook for the small subset of users who care most about
day-one buying. This means we can launch with one retailer (Best Buy) and
"good enough" alert quality — because the platform value carries the
subscription. Payment via LemonSqueezy at $5.99/mo. Free forever for the
platform; Pro for power users. Long-term revenue mix: affiliate (TCGplayer
3.5% on referred sales) + Pro subscriptions.
