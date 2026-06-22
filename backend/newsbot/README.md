# PullList Newsbot

Daily-cron Python bot. Crawls Pokémon TCG news sources, dedupes,
generates English articles with Claude, fact-checks via Tavily, posts
to PullList as drafts. Admin reviews + publishes manually until the
bot has 30 clean days, then auto-publish flips on.

Full design + phase plan: [`SPEC.md`](./SPEC.md).

## Phase 1 status

Single source (PokeBeach HTML scrape via curl_cffi + selectolax),
heuristic classifier, minimum-viable Tavily fact-check, manual
`workflow_dispatch` trigger only (no cron).

## One-time setup

### 1. Run the schema migration

Easiest path — paste these into Neon SQL Editor:

```sql
ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'published';
ALTER TABLE news_posts ADD COLUMN IF NOT EXISTS source_url VARCHAR(512);
CREATE INDEX IF NOT EXISTS idx_news_posts_source_url ON news_posts (source_url);
```

Or run the equivalent script (uses `DATABASE_URL` from
`backend/.env`):

```bash
cd backend
python -m scripts.migrate_news_status_source
```

Both are idempotent — safe to re-run.

### 2. GitHub Actions secrets

Bot reuses the existing `admin@pulllist.org` admin account — no
separate bot user to create. Set the secrets from your terminal so
the plaintext password never passes through a chat or file:

```bash
gh secret set NEWSBOT_ADMIN_EMAIL --body "admin@pulllist.org"
gh secret set NEWSBOT_ADMIN_PASSWORD   # prompts; no echo
gh secret set TAVILY_API_KEY           # optional for first dry-run
```

| Name | Required | Notes |
|---|---|---|
| `PULLLIST_API_BASE` | optional | Defaults to `https://api.pulllist.org/api/v1`. Override for staging. |
| `NEWSBOT_ADMIN_EMAIL` | yes | `admin@pulllist.org` |
| `NEWSBOT_ADMIN_PASSWORD` | yes | Plaintext of the admin password (bot POSTs it to `/auth/login`) |
| `ANTHROPIC_API_KEY` | yes | Already in repo secrets |
| `TAVILY_API_KEY` | yes for live runs | Free tier covers our volume. Bot auto-skips factcheck if unset (useful for first dry-runs) |
| `DAILY_POST_LIMIT` | optional | Default `2` |

**Security note**: bot creds = admin creds. A leaked bot password is a
leaked admin password. Acceptable at friends-beta scale; revisit
(separate bot user) if scope grows.

## Running

### Locally

Create `backend/newsbot/.env`:

```
PULLLIST_API_BASE=https://api.pulllist.org/api/v1
NEWSBOT_ADMIN_EMAIL=admin@pulllist.org
NEWSBOT_ADMIN_PASSWORD=...
ANTHROPIC_API_KEY=...
TAVILY_API_KEY=...
DRY_RUN=1
```

Then:

```bash
cd backend
pip install -r newsbot/requirements.txt
python -m newsbot.main
```

`DRY_RUN=1` runs crawl + login + dedupe + classify + generate +
fact-check, then *logs* what would be posted instead of POSTing.

### In CI

```bash
gh workflow run daily-newsbot.yml -f dry_run=1   # dry
gh workflow run daily-newsbot.yml -f dry_run=0   # live (drafts go to /admin/news)
```

## Pipeline shape

```
sources/pokebeach.py  →  classify.py    →  generator.py     →  factcheck.py  →  publisher.py
   (HTML scrape)        (heuristic)       (Claude Opus)         (Tavily)         (POST draft)
                            │
                            └─ dedupe.py filters by source_url first
```

Each stage is a separate module so Phase 2 can swap pieces (e.g.
Claude classifier for ambiguous cases) without touching the others.

## When to graduate Phase 1 → Phase 2

- 3 consecutive successful `dry_run=1` runs in CI
- 1 successful `dry_run=0` run produces a visible draft in `/admin/news`
- Admin publishes the draft manually + it appears on public `/news`

Then `git tag newsbot-phase-1` and start Phase 2 (multilingual
sweep). See `SPEC.md` for the Phase 2 checklist.
