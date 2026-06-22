# PullList Newsbot

Daily-cron Python bot. Crawls Pokémon TCG news sources, dedupes,
generates English articles with Claude, fact-checks via Tavily, posts
to PullList as drafts. LO reviews + publishes manually until the bot
has 30 clean days, then auto-publish flips on.

Full design + phase plan: [`SPEC.md`](./SPEC.md).

## Phase 1 status

Single source (PokeBeach RSS), heuristic classifier, minimum-viable
Tavily fact-check, manual `workflow_dispatch` trigger only (no cron).

## One-time setup

### 1. Create the bot user in the production DB

```sql
-- Run in Neon SQL Editor AFTER the schema migration. Replace
-- <bcrypt hash> with the output from the python command below.
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

Generate the hash locally:

```bash
python -c "from passlib.context import CryptContext; \
print(CryptContext(schemes=['bcrypt']).hash('YOUR_RANDOM_PASSWORD'))"
```

Drop the same plaintext password into the `NEWSBOT_ADMIN_PASSWORD`
GitHub secret (next step).

### 2. Run the schema migration

```bash
cd backend
python -m scripts.migrate_news_status_source
```

Idempotent — safe to re-run.

### 3. GitHub Actions secrets

In `pulllist` repo → Settings → Secrets → Actions:

| Name | Required | Notes |
|---|---|---|
| `PULLLIST_API_BASE` | optional | Defaults to `https://api.pulllist.org/api/v1`. Override for staging. |
| `NEWSBOT_ADMIN_EMAIL` | yes | `newsbot@pulllist.org` (or whatever you used above) |
| `NEWSBOT_ADMIN_PASSWORD` | yes | The plaintext you bcrypted into the DB |
| `ANTHROPIC_API_KEY` | yes | Already exists in repo secrets |
| `TAVILY_API_KEY` | yes for live | Free tier covers our volume |
| `DAILY_POST_LIMIT` | optional | Default `2` |

## Running

### Locally

Create `backend/newsbot/.env`:

```
PULLLIST_API_BASE=https://api.pulllist.org/api/v1
NEWSBOT_ADMIN_EMAIL=newsbot@pulllist.org
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
   (RSS fetch)         (heuristic)        (Claude Opus)        (Tavily)         (POST draft)
                            │
                            └─ dedupe.py filters by source_url first
```

Each stage is a separate module so Phase 2 can swap pieces (e.g.
Claude classifier for ambiguous cases) without touching the others.

## When to graduate Phase 1 → Phase 2

- 3 consecutive successful `dry_run=1` runs in CI
- 1 successful `dry_run=0` run produces a visible draft in `/admin/news`
- LO publishes the draft manually + it appears on public `/news`

Then `git tag newsbot-phase-1` and start Phase 2 (multilingual
sweep). See `SPEC.md` for the Phase 2 checklist.
