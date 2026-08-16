"""One-off maintenance script: import missing draws and backfill real prize
breakdowns for every draw, then recompute society-key prizes.

Run locally against the dev DB, or on the server after deploy:
    .venv/Scripts/python.exe update_draws_and_prizes.py
"""

import logging
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("update")

from database import SessionLocal, init_db
from models.draw import Draw
from services.euromillions_api import (
    fetch_all_draws_last_n_months,
    fetch_latest_draw,
    fetch_draw_prizes,
)
from services.draw_service import get_draw_by_date, create_draw, get_all_draws
from services.prize_service import get_draw_prizes, save_draw_prizes
from services.my_keys_service import check_society_key_against_draw, get_society_key


def main():
    init_db()
    db = SessionLocal()
    try:
        # 1) Import missing draws (last ~6 months) + their real prize breakdowns
        logger.info("Fetching recent draws...")
        draws = fetch_all_draws_last_n_months(months=8)
        added = 0
        for d in draws:
            if not d or not d.get("numbers"):
                continue
            dd = date.fromisoformat(d["date"])
            if not get_draw_by_date(db, dd):
                prizes = fetch_draw_prizes(d["date"])
                create_draw(
                    db, draw_date=dd, numbers=d["numbers"], stars=d["stars"],
                    prize_total=d.get("prize_total", 0.0), is_manual=False,
                    prizes=prizes,
                )
                added += 1
                logger.info(f"  + draw {dd} (prizes: {len(prizes)} tiers)")
        logger.info(f"Added {added} new draws.")

        # 2) Backfill prize breakdowns for any existing draw missing them
        missing = [dr for dr in get_all_draws(db)
                   if not get_draw_prizes(db, dr.id)]
        logger.info(f"Backfilling prizes for {len(missing)} existing draws...")
        for dr in missing:
            prizes = fetch_draw_prizes(dr.draw_date.isoformat())
            if prizes:
                save_draw_prizes(db, dr.id, prizes)
                logger.info(f"  * {dr.draw_date}: {len(prizes)} tiers")

        # 3) Recompute society-key prizes against every draw
        if get_society_key(db):
            for dr in get_all_draws(db):
                results = check_society_key_against_draw(db, dr.id)
                if results:
                    # Society key won a prize in this draw - add 0.26€ to caixa
                    from services.payment_service import add_to_caixa
                    add_to_caixa(db, 0.26)
                    logger.info(f"  + caixa: added 0.26€ for draw {dr.draw_date} (prize won)")
            logger.info("Society-key prizes recomputed.")
        else:
            logger.info("No society key set — skipping recompute.")

        total = db.query(Draw).count()
        logger.info(f"Done. Total draws in DB: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
