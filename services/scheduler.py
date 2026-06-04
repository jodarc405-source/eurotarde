import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from services.euromillions_api import fetch_latest_draw, fetch_draws_since
from services.draw_service import get_draw_by_date, create_draw
from services.my_keys_service import check_all_my_keys_against_draw
from models.draw import Draw

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def import_draws_from_june_2026():
    """Import all draws from 2026-01-01 onwards. Runs on startup."""
    import asyncio
    logger.info("Importing draws from 2026...")
    try:
        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context, use nest_asyncio or skip
            logger.warning("Cannot import draws: already inside an async event loop. Use the admin import page instead.")
            return
        except RuntimeError:
            pass

        loop = asyncio.new_event_loop()
        draws = loop.run_until_complete(fetch_draws_since(date(2026, 1, 1)))
        loop.close()

        db = SessionLocal()
        added = 0
        try:
            for draw_data in draws:
                if draw_data and draw_data.get("numbers"):
                    existing = get_draw_by_date(db, draw_data["date"])
                    if not existing:
                        new_draw = create_draw(
                            db,
                            draw_date=draw_data["date"],
                            numbers=draw_data["numbers"],
                            stars=draw_data["stars"],
                            prize_total=draw_data.get("prize_total", 0.0),
                            is_manual=False,
                        )
                        added += 1
                        # Auto-check my keys against the new draw
                        check_all_my_keys_against_draw(db, new_draw.id)
            logger.info(f"Import complete: {added} new draws added from 2026.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error importing draws: {e}")


def update_draws():
    """Job to update Euromillions draws. Called by scheduler every Wed & Sun."""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        draw_data = loop.run_until_complete(fetch_latest_draw())
        loop.close()

        if draw_data and draw_data.get("numbers"):
            db = SessionLocal()
            try:
                existing = get_draw_by_date(db, draw_data["date"])
                if not existing:
                    new_draw = create_draw(
                        db,
                        draw_date=draw_data["date"],
                        numbers=draw_data["numbers"],
                        stars=draw_data["stars"],
                        prize_total=draw_data.get("prize_total", 0.0),
                        is_manual=False,
                    )
                    logger.info(f"New draw added for {draw_data['date']}")

                    # Auto-check my keys against the new draw
                    wins = check_all_my_keys_against_draw(db, new_draw.id)
                    winning = [w for w in wins if w["prize"] > 0]
                    if winning:
                        logger.info(f"MY KEYS WON! {len(winning)} key(s) matched!")
                else:
                    logger.info(f"Draw for {draw_data['date']} already exists, skipping.")
            finally:
                db.close()
        else:
            logger.warning("Could not fetch latest draw data.")
    except Exception as e:
        logger.error(f"Error in update_draws job: {e}")


def start_scheduler():
    """Start the APScheduler with all jobs."""
    # Import draws from June 2026 on startup
    import_draws_from_june_2026()

    # Regular job: Wednesday and Sunday at 00:00
    scheduler.add_job(
        update_draws,
        trigger=CronTrigger(day_of_week="wed,sun", hour=0, minute=0),
        id="update_draws",
        name="Update Euromillions Draws",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Draws will update Wed & Sun at 00:00.")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
