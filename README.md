# PullList

Pokémon TCG catalog + collection tracker.

Live at [pulllist.org](https://pulllist.org).

Stack:
- **Backend**: FastAPI + SQLAlchemy (async) + SQLite (swap to Postgres later)
- **Frontend**: Next.js 15 (App Router) + TypeScript + Tailwind
- **Data source**: [pokemontcg.io](https://pokemontcg.io) (free API)

---

## Structure

```
PullList/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # settings (.env loader)
│   │   ├── database.py       # async engine + session
│   │   ├── models/           # Set, Card SQLAlchemy models
│   │   ├── schemas/          # Pydantic response models
│   │   └── api/routes.py     # /sets, /cards, /health
│   ├── scripts/
│   │   └── seed_sets.py      # pull catalog from pokemontcg.io
│   ├── requirements.txt
│   └── .env                  # local config (gitignored)
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # home
│   │   └── sets/page.tsx     # set browser
│   ├── lib/api.ts            # backend client
│   └── package.json
└── README.md
```

---

## First run

### 1. Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1   # venv already created during setup
uvicorn app.main:app --reload --port 8000
```

API live at `http://localhost:8000`. Auto docs at `http://localhost:8000/docs`.

### 2. Seed the catalog (one-time, ~30s for sets only)

In a second terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m scripts.seed_sets --sets-only
```

This pulls every Pokémon TCG set ever printed (~170 sets, set logos + metadata).

For full card data (~20,000 cards, takes 10–15 min):

```powershell
python -m scripts.seed_sets
```

Or just one set to start:

```powershell
python -m scripts.seed_sets --set sv8     # Surging Sparks
python -m scripts.seed_sets --set sv8pt5  # Prismatic Evolutions
```

### 3. Frontend

In a third terminal:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`.

---

## What works now

- ✅ Home page with live API health check
- ✅ `/sets` page — browse all seeded sets, grouped by series
- ✅ Backend API: `/api/v1/health`, `/sets`, `/sets/{id}`, `/sets/{id}/cards`, `/cards/{id}`, `/cards/search`
- ✅ pokemontcg.io seed script (sets + cards + prices)
- ✅ Dark mode UI with retailer color tokens locked in
- ✅ SQLite DB — zero install, file at `backend/pulllist.db`

## What's next (in order)

1. Set detail page `/sets/[id]` — card grid for a single set
2. Card detail page `/cards/[id]` — single card with prices, image, market data
3. Collection tracker — login + "I have this" toggle + completion %
4. Stock tracker module — port `BoT/monitor.py` workers into `backend/app/workers/`
5. Map view `/map` — Leaflet + retailer markers
6. Alert builder + Discord webhook push

## Migrating to Postgres later

When SQLite gets cramped (10k+ users), swap `DATABASE_URL` in `.env`:

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/pulllist
```

No code changes needed. Run seed script again.

## Optional: pokemontcg.io API key

Free for low volume, but a key lifts rate limits. Grab one at
[dev.pokemontcg.io](https://dev.pokemontcg.io) and put it in `backend/.env`:

```
POKEMONTCG_API_KEY=your_key_here
```
