#!/usr/bin/env bash
# Polls the DB for backfill idleness; once the monthly pass has been
# quiet for two consecutive 3-minute windows, kicks off the weekly pass.
#
# Robust against the actual completion signal we can observe externally:
# rising tcg snapshot count means v5 still alive; flat count for 6+ min
# means the long-running script either finished its summary log line
# OR died — either way the right move is to launch weekly mode.

set -u
cd "$(dirname "$0")/.."

LOG=backfill_weekly.log
prev=-1
quiet=0

echo "[$(date)] waiter armed" > "$LOG"

while true; do
  cur=$(python - <<'PY' 2>/dev/null
import asyncio
from sqlalchemy import func, select
from app.database import SessionLocal, init_db
from app.models import CardPriceSnapshot

async def main():
    await init_db()
    async with SessionLocal() as db:
        n = (await db.execute(
            select(func.count(CardPriceSnapshot.id)).where(
                CardPriceSnapshot.source == "tcgplayer"
            )
        )).scalar() or 0
        print(n)

asyncio.run(main())
PY
)
  cur=${cur:-0}
  ts=$(date +%H:%M:%S)
  if [ "$cur" = "$prev" ]; then
    quiet=$((quiet + 1))
    echo "[$ts] flat at $cur (quiet=$quiet)" >> "$LOG"
  else
    quiet=0
    echo "[$ts] grew $prev -> $cur" >> "$LOG"
  fi
  prev=$cur
  if [ "$quiet" -ge 2 ]; then
    echo "[$ts] monthly pass idle -> launching weekly" >> "$LOG"
    break
  fi
  sleep 180
done

echo "[$(date)] starting weekly pass" >> "$LOG"
exec python -m scripts.backfill_tcg_history \
  --min-price 5 --throttle-ms 400 --weekly --no-resume >> "$LOG" 2>&1
