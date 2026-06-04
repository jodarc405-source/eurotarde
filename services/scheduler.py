import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal
from services.euromillions_api import fetch_latest_draw
from services.draw_service import create_draw, get_draw_by_date

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


async def update_draws():
    """Fetch latest draw from API and store in database."""
    logger.info("Running scheduled draw update...")
    try:
        draw_data = await fetch_latest_draw()
        if not draw_data:
            logger.warning("No draw data returned from API")
            return

        db = SessionLocal()
        try:
            existing = get_draw_by_date(db, draw_data["date"])
            if existing:
                logger.info(f"Draw for {draw_data['date']} already exists, skipping")
                return

            create_draw(
                db=db,
                draw_date=draw_data["date"],
                numbers=draw_data["numbers"],
                stars=draw_data["stars"],
                prize_total=draw_data.get("prize_total", 0.0),
                is_manual=False,
            )
            logger.info(f"Successfully added draw for {draw_data['date']}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error updating draws: {e}")


def start_scheduler():
    """Start the background scheduler."""
    if not scheduler.running:
        scheduler.add_job(
            update_draws,
            trigger=CronTrigger(day_of_week="wed,sun", hour=0, minute=0),
            id="update_draws",
            name="Update Euromillions Draws",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("Scheduler started - draws updated Wed & Sun at 00:00")


def stop_scheduler():
    """Stop the background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
