# PullList Newsbot — Spec & Handoff

**Status:** Phase 1 shipped 2026-06-25 (tag `newsbot-phase-1`). Phase 2 in progress.
**Designed:** 2026-06-22 · **Phase 1 live:** 2026-06-25

---

## Kickoff prompt for a fresh session

> Read `backend/newsbot/SPEC.md` and resume from current phase.

That's it. The "Phase 1 reality" section below tells you what diverged from the original plan during implementation — read it before assuming any code matches the original SPEC sections verbatim.

---

## Phase 1 reality — what shipped vs original SPEC

Several decisions changed during the Phase 1 build. The original SPEC sections below ("Schema changes", "Sources", "Stack", etc.) describe the plan; this table captures what actually landed in `main`:

| Original SPEC | Phase 1 implementation | Why |
|---|---|---|
| Scrapling `Fetcher` (httpx-based) | Scrapling `AsyncStealthySession(solve_cloudflare=True)` — full headless Chromium | PokeBeach article pages 403 plain httpx + curl_cffi alone on JS challenge |
| PokeBeach RSS at `/news/feed` | HTML scrape of `https://www.pokebeach.com/` homepage (16 `article.post` cards/page) | PokeBeach `/feed` returns 500 upstream, `/news/feed` 404s |
| Claude Opus 4.8 + adaptive thinking | Claude Sonnet 4.6 medium effort + adaptive thinking | ~6× cheaper (~$0.012-0.05/article vs $0.075); Sonnet handles 400-word news well |
| Dedicated `newsbot@pulllist.org` user | Reuses existing `admin@pulllist.org` (env-overridable) | One less mailbox / account to rotate |
| Prompt-only JSON output contract | `output_config.format` schema + greedy `{…}` regex + Pydantic validate (defence in depth) | 33% drop rate on prompt-only; structured outputs eliminates JSON parse failures |
| Phase 3 cron flip (later) | Cron live end of Phase 1 (12:00 UTC daily = 8am ET) | Stable across multi-run testing, no reason to delay |
| (not in SPEC) | All external images proxied through `images.weserv.nl` | Hot-link-protected sources 403 cross-origin Referer — see `project-pulllist-weserv-images` memory |
| (not in SPEC) | ASCII-only slugs via NFKD + ASCII strip | Unicode in slug caused Next.js + FastAPI URL-encoding mismatch → 404s |
| (not in SPEC) | Body image extraction (figures + bare `<img>`, cap 10) | Set-reveal articles put 10-20+ card art shots as bare img tags outside figures |
| (not in SPEC) | Paired-image auto-detection → `<div style="display:flex;gap:0">` HTML for split cards | Pokémon TCG split-card sets (LEGEND, split Stadium etc.) need adjacent rendering |
| (not in SPEC) | Admin tooling: draft preview route, row-level delete, `admin-{dump,delete,proxy-thumbnails}-post.yml` workflows | Friction reduction during draft review |

Operationally on `main`:
- Cron: `.github/workflows/daily-newsbot.yml` → 12:00 UTC daily, manual `workflow_dispatch` with `dry_run` + `post_limit` inputs.
- Stack: `scrapling[fetchers]>=0.3`, `anthropic>=0.50`, `tavily-python>=0.5`, `pydantic>=2.5`, `httpx`, `pydantic-settings`.
- Default settings: `claude_model=claude-sonnet-4-6`, `claude_effort=medium`, `daily_post_limit=2`, `bot_author_name="PullList Bot"`.
- Render free-tier cold-start: `publisher.REQUEST_TIMEOUT=90.0` (see `project-pulllist-render-cold-start` memory).

---

## What this is

A daily-cron Python bot that:

1. Crawls a fixed list of Pokémon TCG news sources
2. Dedupes against existing posts (via `source_url`)
3. Picks the 1–3 best items of the day
4. Generates an English news article (Markdown) via Claude
5. Fact-checks key claims via Tavily
6. Publishes to PullList as a **draft** (LO reviews + publishes manually for now)

Runs on **GitHub Actions free tier**. Lives in `backend/newsbot/`. Talks to PullList only via the public REST API — no shared imports with the backend app.

---

## Why draft mode

- Bot can produce factually wrong text → don't broadcast unverified content to users and AdSense.
- 30 seconds of LO eyes-on per post is cheap insurance.
- After ~30 days clean, flip default to auto-publish.

---

## Stack (final)

| Concern | Choice | Why |
|---|---|---|
| Crawl | **Scrapling** (D4Vinci/Scrapling) | Stealth fetcher + adaptive selectors that survive HTML changes |
| Search / fact-check | **Tavily** | Built for agents, returns cite_url, free tier covers our volume |
| LLM | **Anthropic SDK + Claude Opus 4.8 + adaptive thinking** | Quality matters for SEO / AdSense; volume is tiny |
| HTTP to PullList | **httpx (async)** | Same shape as backend |
| Schedule | **GitHub Actions cron** | Free, no extra infra |

**Rejected:**
- Agent Browser — posting to our own API doesn't need a browser.
- Web Search skill — duplicates Tavily.

**Capability Evolver** — kept on the shelf for long-term iteration tooling, not part of Phase 1.

---

## Schema changes (Phase 1)

Both ALTERs are idempotent.

```sql
ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'published';
ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS source_url VARCHAR(512);
CREATE INDEX IF NOT EXISTS idx_news_posts_source_url ON news_posts (source_url);
```

- `status`: `'draft'` | `'published'`. Existing posts grandfather to `'published'`.
- `source_url`: only set by bot. Exact-match dedupe key.
- Index makes dedupe lookup O(log n).

### Backend API changes

| Endpoint | Change |
|---|---|
| `GET /news/posts` | Default filter `status='published'`. Admin token can pass `?include_drafts=true` to see all. |
| `GET /news/posts/source-urls` (NEW) | Admin-only. Returns `{url: slug}` map for dedupe. |
| `GET /news/posts/{slug}` | Returns post regardless of status if requester is admin; non-admin gets 404 on drafts. |
| `POST /news/posts` | Accepts optional `status` + `source_url`. Status defaults `'published'`. Bot always sends `'draft'`. |
| `PUT /news/posts/{slug}` | Same as POST. |

### Frontend changes (Phase 1)

- `frontend/lib/news.ts` `NewsPost` type: add `status?: string`, `source_url?: string | null`.
- `/admin/news` list: badge **"DRAFT"** on rows where `status==='draft'`.
- `PostForm.tsx`: Status dropdown (Draft / Published). One-click "Publish" button on the row in `/admin/news` for fast review.

---

## Sources

### Phase 1 — bring-up

| Source | URL | Notes |
|---|---|---|
| **PokeBeach** | https://www.pokebeach.com/news | Highest-volume TCG news in EN. RSS at `/news/feed`. |

### Phase 2 — multilingual sweep

| Source | URL | Lang | Default category | Notes |
|---|---|---|---|---|
| Bulbanews | https://bulbanews.bulbagarden.net | EN | `tcg` / `news` | MediaWiki RSS |
| Pokemon.com news | https://www.pokemon.com/us/pokemon-news | EN | `news` / `drops` | Official |
| Pokémon Center blog | https://www.pokemoncenter.com/category/news | EN | `center` | US drops + merch |
| pokemon-card.com | https://www.pokemon-card.com/info/ | JP | `drops` / `tcg` | Official JP TCG site |
| pokemonkorea.co.kr | https://pokemonkorea.co.kr/news | KR | `news` / `drops` | Official KR |
| Reddit r/pkmntcgcollections | https://www.reddit.com/r/pkmntcgcollections/.json | EN | `market` | Public JSON; respect rate limit |

**Output is always English** even when source is JP/KR. Claude translates + rewrites in the generator step.

### Phase 3 — optional expansion (only if Phase 2 stable for 14 days)

- inven.co.kr 포켓몬 게시판
- Famitsu TCG
- Bleeding Cool TCG
- pokemonmillennium.net

---

## Category mapping

Bot picks one of: `drops` | `market` | `tcg` | `center` | `guide` | `news`.

Claude classifier handles ambiguous cases. Heuristic fallback:

| Signal in title/body | Category |
|---|---|
| "release", "pre-order", "drops", "available", "launches" | `drops` |
| "price", "trending", "value", "market", "spike", "crash" | `market` |
| "set", "deck", "tournament", "Worlds", "Regionals", "meta" | `tcg` |
| "Pokémon Center", "exclusive", "in-store" | `center` |
| "how to", "guide", "tips", "best", "tier list" | `guide` |
| anything else | `news` |

---

## Env vars / GitHub Actions secrets

Put these in `pulllist` repo → Settings → Secrets → Actions:

| Name | Purpose |
|---|---|
| `PULLLIST_API_BASE` | Default `https://api.pulllist.org/api/v1` — override for staging |
| `NEWSBOT_ADMIN_EMAIL` | Dedicated bot admin user email (create in Phase 1) |
| `NEWSBOT_ADMIN_PASSWORD` | Bot password (16+ char random) |
| `ANTHROPIC_API_KEY` | Already exists in repo secrets |
| `TAVILY_API_KEY` | New — sign up at tavily.com, free tier |
| `DAILY_POST_LIMIT` | Default `2` |
| `DRY_RUN` | Set `"1"` to skip the publish step (used for testing in CI) |

### Bot user setup (one-time, Phase 1)

```sql
-- Run in Neon SQL Editor after the schema migration
INSERT INTO users (id, email, password_hash, name, is_admin, created_at)
VALUES (
  gen_random_uuid(),
  'newsbot@pulllist.org',
  '<bcrypt hash>',
  'PullList Bot',
  TRUE,
  NOW()
);
```

Generate the bcrypt hash with:

```bash
python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('YOUR_PASSWORD'))"
```

Paste the hash into the INSERT above. Then drop the password into the GH secret. Bot logs in fresh every run, so JWT TTL is a non-issue.

---

## File layout

```
backend/newsbot/
├── SPEC.md                  # this file
├── README.md                # run/test instructions (build in Phase 1)
├── requirements.txt         # scrapling, anthropic, tavily-python, httpx, pydantic
├── config.py                # env loading + settings
├── sources/
│   ├── __init__.py          # SOURCES registry + crawl_all()
│   ├── pokebeach.py         # Phase 1
│   ├── bulbanews.py         # Phase 2
│   ├── pokemoncard_jp.py    # Phase 2
│   ├── pokemonkorea_kr.py   # Phase 2
│   ├── pokemoncenter.py     # Phase 2
│   ├── pokemon_com.py       # Phase 2
│   └── reddit_tcg.py        # Phase 2
├── dedupe.py                # filter_unseen() — checks source_url via API
├── classify.py              # category picker (Claude or heuristic)
├── generator.py             # generate_article() — Claude + PullList style guide
├── factcheck.py             # verify_claims() — Tavily
├── publisher.py             # login + POST to /news/posts
└── main.py                  # orchestration entry point

.github/workflows/
└── daily-newsbot.yml        # cron: 12:00 UTC daily, manual_dispatch enabled
```

---

## Phase plan

### Phase 1 — Bring-up (1 PR)

- [ ] `backend/scripts/migrate_news_status_source.py` — idempotent ALTERs
- [ ] Backend: `status` + `source_url` columns on `NewsPost` model
- [ ] Backend: `GET /news/posts` filters by status, supports `?include_drafts=true` for admin
- [ ] Backend: `GET /news/posts/source-urls` (admin-only)
- [ ] Backend: `POST` / `PUT /news/posts` accept `status` + `source_url`
- [ ] Frontend: `NewsPost` type + DRAFT badge in `/admin/news` + Status dropdown in `PostForm` + one-click Publish on row
- [ ] Newsbot: `requirements.txt`, `config.py`, `sources/pokebeach.py`, `dedupe.py`, `classify.py`, `generator.py`, `factcheck.py`, `publisher.py`, `main.py`
- [ ] GitHub Actions: `daily-newsbot.yml` with `manual_dispatch` only (no cron yet)
- [ ] Create `newsbot@pulllist.org` bot user via SQL
- [ ] Test: `gh workflow run daily-newsbot.yml -f dry_run=1` → crawl + classify succeeds
- [ ] Test: same workflow with `dry_run=0` → single draft visible in `/admin/news`
- [ ] LO publishes the draft manually → confirms it appears on public `/news`
- [ ] Commit, tag `newsbot-phase-1`

### Phase 2 — Source expansion (in progress)

Driven by an observation during Phase 1: PokeBeach alone misses platform-specific drop info (BestBuy SKUs, Pokémon Center exclusives, Target/Walmart preorders) that lives in retailer announcements and community deal threads. Two-track expansion:

**Track A: Search-driven discovery (priority)**

Bot proactively finds new content via web search rather than relying only on hard-coded source crawlers. Reuses the existing Tavily account (already in deps for fact-check). Tavily free tier covers our volume.

- [ ] `sources/web_search.py` — for each configured query, hit Tavily, filter by recency + domain allowlist, build NewsItem list
- [ ] Settings: `web_search_enabled`, `web_search_queries` (list), `web_search_days_back`, `web_search_max_per_query`, `web_search_allowed_domains`
- [ ] Generic page enricher: fetch with curl_cffi, extract `og:image` as hero + `<main>` / `<article>` / `og:description` as body. No per-domain selectors.
- [ ] Generator prompt branch: detect drop/product pages (host in retailer list) → tighter format (150-250w, SKU/price/limit prominent) vs editorial default
- [ ] Conservative defaults: 1 query/day, 5 results, top 3 allowed domains (bestbuy.com, pokemoncenter.com, target.com, etc.) — ~$2/mo extra
- [ ] Iterate query design once we see real result quality

**Track B: Known-source crawlers** (original SPEC list, lower priority)

- [ ] Sources: bulbanews, pokemoncard_jp, pokemonkorea_kr, pokemoncenter, pokemon_com
- [ ] Generator: detect source language, prompt Claude to translate + rewrite into English (Output is always English regardless of source)
- [ ] Classify: heuristic per source (Pokémon Center → `center`, pokemoncard_jp drops → `drops`)
- [ ] Test each source individually
- [ ] **Reddit r/pkmntcgcollections** moved to "skip" — Track A's search-driven path catches the same retail drops Reddit aggregates, without the spam/karma filtering complexity

### Phase 3 — Cron activation ✅ shipped end of Phase 1

- [x] Workflow: `schedule: '0 12 * * *'` (12:00 UTC = 21:00 KST = 8am ET) — see `.github/workflows/daily-newsbot.yml`
- [ ] **Still open**: failure alert (3 consecutive failed runs → Discord webhook or Resend email) — deferred until a real noise pattern emerges
- [ ] Monitor 14 days — currently mid-window

### Phase 4 — Future (not committed)

- Auto-publish if dry-runs show <2% factual error rate (Tavily fact-check must be wired up first — currently `skip_factcheck` auto-engages when `TAVILY_API_KEY` is unset)
- Twitter / X as source (paid API — gate on traffic)
- Thumbnail image generation
- SEO-tuned meta tags
- Listing pagination (`/news` page) once post count crosses ~30

---

## Operational notes

### Dedupe logic

```python
async def filter_unseen(items, token):
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{settings.api_base}/news/posts/source-urls",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        seen = set(r.json().keys())
    return [i for i in items if i.url not in seen]
```

### Fact-check policy

For each generated article, extract 1–3 key factual claims (e.g. "Surging Sparks SAR Pikachu hit $200 last week"). Send each to Tavily search.

- **0 of N** results corroborate within 30% accuracy → reject (skip, don't store).
- **1+** corroborate → publish as draft.

The bot logs every claim + result for debugging.

### Cost estimate (monthly)

| Item | Cost |
|---|---|
| Claude Opus 4.8: ~2 articles × (6k input + 3k output) / day | ~$6 |
| Tavily: ~10 searches/day | $0 (free tier) |
| Scrapling: stateless | $0 |
| GitHub Actions: ~5 min/day × 30 = 150 min < 2,000 free | $0 |
| **Total** | **~$6/mo** |

### Bot generation style

Generator system prompt references PullList's existing post tone — terse, informative, English only, no fluff. Body format:

```markdown
[Lead paragraph — 2-3 sentences. The actual news.]

## What happened

- Fact one with source attribution
- Fact two
- Fact three

## Why it matters for collectors

[1-2 paragraph analysis tied to PullList's data: pricing trends,
set context, collectibility angle.]

## Sources

- [Source name](https://...)
```

Target length: **400–700 words**.

---

## Known landmines

| Landmine | Mitigation |
|---|---|
| Scrapling browser modes need `playwright install` (~300MB CI image) | Use only `Fetcher` (httpx-based) in Phase 1. Browser modes only if a source demands them. |
| pokemonkorea.co.kr is JS-heavy | Try `StealthyFetcher` (curl_cffi). Fall back to mobile UA + plain httpx — KR mobile build is lighter. |
| pokemon-card.com may show age gate | Send `Cookie: AGE_VERIFY=1` or equivalent — confirm in Phase 2 dev. |
| Bot JWT lifetime | Bot logs in every run; never caches token across runs. |
| Bot 401 cascades silently | Bot logs the exact `/auth/login` error in CI. If 401, LO rotates `NEWSBOT_ADMIN_PASSWORD` and updates the GH secret. |
| Source HTML changes break parser | Scrapling adaptive selectors auto-relink. If all sources fail one day, CI cron-failure email alerts LO. |
| Claude hallucinates a price / date | Fact-check rejects. Repeated rejects = source quality issue, retune prompt. |
| AdSense flags AI content | Articles always cite sources + add commentary. AdSense doesn't ban AI content — it flags low-quality. Quality > volume. |
| Reddit JSON returns 429 without OAuth | Throttle to 1 request / 2 seconds. If 429 persists, drop Reddit from Phase 2 — not worth paid API. |
| pokemon-card.com Japanese content needs translation accuracy check | Generator prompt explicitly asks Claude for "literal-then-natural" translation; fact-check verifies any date/price still. |

---

## When Phase 1 is ready to merge

1. `gh workflow run daily-newsbot.yml -f dry_run=1` succeeds in CI.
2. Same workflow with `dry_run=0` produces a single draft post visible in `/admin/news` with the DRAFT badge.
3. LO manually publishes the draft and it appears on public `/news`.
4. No errors in CI logs across 3 consecutive runs.

Then merge, tag `newsbot-phase-1`, move to Phase 2.

---

## Open questions for the new session to clarify with LO

- Bot's author display name: **"PullList Bot"** / "PullList" / something else?
- Bot avatar in `/admin/users`: skip for Phase 1 (probably).
- Cron time: 12:00 UTC = 21:00 KST. Acceptable?
- Reddit in Phase 2: include public JSON, or skip entirely until paid API?
- Should the dedupe key also consider **title similarity** (Levenshtein > 0.85) in addition to exact `source_url` match? Same story syndicated across PokeBeach + Bulbanews would otherwise post twice.
