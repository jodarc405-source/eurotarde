import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from services.euromillions_api import fetch_latest_draw, fetch_all_draws_last_n_months
from services.draw_service import get_draw_by_date, create_draw
from services.my_keys_service import (
    check_all_my_keys_against_draw,
    check_society_key_against_draw,
    get_distinct_user_ids_with_keys,
)
from models.draw import Draw

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def import_recent_draws():
    """Import draws from the last 6 months (and fill any gaps up to today).
    Runs on startup.
    """
    logger.info("Importing recent Euromillions draws...")
    try:
        draws = fetch_all_draws_last_n_months(months=6)
        if not draws:
            logger.warning("No draws returned from import.")
            return

        db = SessionLocal()
        added = 0
        try:
            for draw_data in draws:
                if not draw_data or not draw_data.get("numbers"):
                    continue
                draw_date = date.fromisoformat(draw_data["date"])
                existing = get_draw_by_date(db, draw_date)
                if not existing:
                    new_draw = create_draw(
                        db,
                        draw_date=draw_date,
                        numbers=draw_data["numbers"],
                        stars=draw_data["stars"],
                        prize_total=draw_data.get("prize_total", 0.0),
                        is_manual=False,
                    )
                    added += 1
                    # Check society key against the new draw only (no double-counting)
                    check_society_key_against_draw(db, new_draw.id)
            logger.info(f"Import complete: {added} new draws added.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error importing draws: {e}")


def update_draws():
    """Job to update Euromillions draws.

    Called by scheduler every day at 21:00. Fetches the latest draw and,
    if it is a new draw date, adds it. Also fills any missing draws between
    the last stored draw and today (so the list is always up to date).
    """
    logger.info("Running scheduled draw update...")
    try:
        # 1) Fetch and add the latest draw if new
        draw_data = fetch_latest_draw()
        if draw_data and draw_data.get("numbers"):
            db = SessionLocal()
            try:
                draw_date = date.fromisoformat(draw_data["date"])
                existing = get_draw_by_date(db, draw_date)
                if not existing:
                    new_draw = create_draw(
                        db,
                        draw_date=draw_date,
                        numbers=draw_data["numbers"],
                        stars=draw_data["stars"],
                        prize_total=draw_data.get("prize_total", 0.0),
                        is_manual=False,
                    )
                    logger.info(f"New draw added for {draw_date}")
                    check_society_key_against_draw(db, new_draw.id)
                else:
                    logger.info(f"Draw for {draw_date} already exists, skipping.")
            finally:
                db.close()
        else:
            logger.warning("Could not fetch latest draw data.")

        # 2) Fill any gaps: re-import last 6 months to catch missed draws
        import_recent_draws()
    except Exception as e:
        logger.error(f"Error in update_draws job: {e}")


def start_scheduler():
    """Start the APScheduler with all jobs."""
    import_recent_draws()

    # Euromillions draws happen Tuesday & Friday ~20:00 CET.
    # We check daily at 21:00 to ensure results are available and
    # to fill any gaps so the draws list stays current up to today.
    scheduler.add_job(
        update_draws,
        trigger=CronTrigger(day_of_week="mon,tue,wed,thu,fri,sat,sun", hour=21, minute=0),
        id="update_draws",
        name="Update Euromillions Draws",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Draws will update every day at 21:00.")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
