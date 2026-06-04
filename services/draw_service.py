import json
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from models.draw import Draw


def create_draw(db: Session, draw_date: date, numbers: list[int], stars: list[int],
                prize_total: float = 0.0, is_manual: bool = False) -> Draw:
    draw = Draw(
        draw_date=draw_date,
        numbers=json.dumps(sorted(numbers)),
        stars=json.dumps(sorted(stars)),
        prize_total=prize_total,
        is_manual=is_manual,
    )
    db.add(draw)
    db.commit()
    db.refresh(draw)
    return draw


def get_draw_by_id(db: Session, draw_id: int) -> Draw | None:
    return db.query(Draw).filter(Draw.id == draw_id).first()


def get_draw_by_date(db: Session, draw_date: date) -> Draw | None:
    return db.query(Draw).filter(Draw.draw_date == draw_date).first()


def get_draws(db: Session, week: int = None, month: int = None, year: int = None,
              page: int = 1, per_page: int = 50) -> list[Draw]:
    query = db.query(Draw).order_by(Draw.draw_date.desc())

    if year:
        query = query.filter(extract("year", Draw.draw_date) == year)
    if month:
        query = query.filter(extract("month", Draw.draw_date) == month)
    if week:
        # ISO week number
        query = query.filter(extract("week", Draw.draw_date) == week)

    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page).all()


def get_all_draws(db: Session) -> list[Draw]:
    return db.query(Draw).order_by(Draw.draw_date.desc()).all()


def get_draw_count(db: Session, week: int = None, month: int = None, year: int = None) -> int:
    query = db.query(func.count(Draw.id))
    if year:
        query = query.filter(extract("year", Draw.draw_date) == year)
    if month:
        query = query.filter(extract("month", Draw.draw_date) == month)
    if week:
        query = query.filter(extract("week", Draw.draw_date) == week)
    return query.scalar()


def delete_draw(db: Session, draw_id: int) -> bool:
    draw = db.query(Draw).filter(Draw.id == draw_id).first()
    if draw:
        db.delete(draw)
        db.commit()
        return True
    return False


def get_available_years(db: Session) -> list[int]:
    years = db.query(extract("year", Draw.draw_date)).distinct().order_by(
        extract("year", Draw.draw_date).desc()
    ).all()
    return [int(y[0]) for y in years if y[0]]


def get_distinct_years(db: Session) -> list[int]:
    return get_available_years(db)


def get_distinct_months(db: Session, year: int = None) -> list[int]:
    query = db.query(extract("month", Draw.draw_date)).distinct()
    if year:
        query = query.filter(extract("year", Draw.draw_date) == year)
    months = query.order_by(extract("month", Draw.draw_date)).all()
    return [int(m[0]) for m in months]
