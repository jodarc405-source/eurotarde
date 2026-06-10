import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from services.euromillions_api import fetch_latest_draw, fetch_all_draws_last_n_months
from services.draw_service import get_draw_by_date, create_draw
from services.my_keys_service import check_all_my_keys_against_draw
from models.draw import Draw

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def import_recent_draws():
    """Import draws from the last 6 months. Runs on startup."""
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
                    check_all_my_keys_against_draw(db, new_draw.id)
            logger.info(f"Import complete: {added} new draws added.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error importing draws: {e}")


def update_draws():
    """Job to update Euromillions draws. Called by scheduler every Tue & Fri at 21:00."""
    logger.info("Running scheduled draw update...")
    try:
        draw_data = fetch_latest_draw()
        if not draw_data or not draw_data.get("numbers"):
            logger.warning("Could not fetch latest draw data.")
            return

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

                wins = check_all_my_keys_against_draw(db, new_draw.id)
                winning = [w for w in wins if w["prize"] > 0]
                if winning:
                    logger.info(f"MY KEYS WON! {len(winning)} key(s) matched!")
            else:
                logger.info(f"Draw for {draw_date} already exists, skipping.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in update_draws job: {e}")


def start_scheduler():
    """Start the APScheduler with all jobs."""
    import_recent_draws()

    # Euromillions draws happen Tuesday & Friday ~20:00 CET
    # We check at 21:00 to ensure results are available
    scheduler.add_job(
        update_draws,
        trigger=CronTrigger(day_of_week="tue,fri", hour=21, minute=0),
        id="update_draws",
        name="Update Euromillions Draws",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started. Draws will update Tue & Fri at 21:00.")


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
