"""Page view analytics services."""
from datetime import date, timedelta
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session
from models.page_view import PageView


def get_total_views(db: Session) -> int:
    """Get total number of page views."""
    return db.query(PageView).count()


def get_today_views(db: Session) -> int:
    """Get number of page views today."""
    return db.query(PageView).filter(PageView.view_date == date.today()).count()


def get_views_this_week(db: Session) -> int:
    """Get number of page views this week (last 7 days)."""
    week_ago = date.today() - timedelta(days=7)
    return db.query(PageView).filter(PageView.view_date >= week_ago).count()


def get_views_this_month(db: Session) -> int:
    """Get number of page views this month."""
    return db.query(PageView).filter(
        func.extract("month", PageView.view_date) == date.today().month,
        func.extract("year", PageView.view_date) == date.today().year,
    ).count()


def get_unique_visitors_today(db: Session) -> int:
    """Get number of unique visitors today (by IP)."""
    return db.query(distinct(PageView.ip_address)).filter(
        PageView.view_date == date.today()
    ).count()


def get_unique_visitors_total(db: Session) -> int:
    """Get total number of unique visitors (by IP)."""
    return db.query(distinct(PageView.ip_address)).count()


def get_top_pages(db: Session, limit: int = 10) -> list[dict]:
    """Get most viewed pages."""
    results = (
        db.query(PageView.path, func.count(PageView.id).label("views"))
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(limit)
        .all()
    )
    return [{"path": r[0], "views": r[1]} for r in results]


def get_views_last_7_days(db: Session) -> list[dict]:
    """Get views per day for the last 7 days."""
    week_ago = date.today() - timedelta(days=6)
    results = (
        db.query(PageView.view_date, func.count(PageView.id).label("views"))
        .filter(PageView.view_date >= week_ago)
        .group_by(PageView.view_date)
        .order_by(PageView.view_date)
        .all()
    )
    # Fill in missing days with 0
    data = {}
    for i in range(7):
        d = (week_ago + timedelta(days=i)).isoformat()
        data[d] = 0
    for r in results:
        data[r[0].isoformat()] = r[1]
    return [{"date": k, "views": v} for k, v in data.items()]
