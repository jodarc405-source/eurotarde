from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.payment import Payment


def create_payment(db: Session, user_id: int, draw_id: int | None, amount: float, payment_date: date, notes: str | None = None) -> Payment:
    payment = Payment(
        user_id=user_id,
        draw_id=draw_id,
        amount=amount,
        payment_date=payment_date,
        notes=notes,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_payment_by_id(db: Session, payment_id: int) -> Payment | None:
    return db.query(Payment).filter(Payment.id == payment_id).first()


def get_payments(db: Session, user_id: int | None = None, draw_id: int | None = None) -> list[Payment]:
    query = db.query(Payment).order_by(Payment.payment_date.desc())
    if user_id:
        query = query.filter(Payment.user_id == user_id)
    if draw_id:
        query = query.filter(Payment.draw_id == draw_id)
    return query.all()


def get_all_payments(db: Session) -> list[Payment]:
    return db.query(Payment).order_by(Payment.payment_date.desc()).all()


def get_payments_by_user(db: Session, user_id: int) -> list[Payment]:
    return db.query(Payment).filter(Payment.user_id == user_id).order_by(Payment.payment_date.desc()).all()


def get_payments_by_draw(db: Session, draw_id: int) -> list[Payment]:
    return db.query(Payment).filter(Payment.draw_id == draw_id).order_by(Payment.payment_date.desc()).all()


def update_payment(db: Session, payment_id: int, amount: float | None = None, payment_date: date | None = None, notes: str | None = None) -> Payment | None:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment:
        if amount is not None:
            payment.amount = amount
        if payment_date is not None:
            payment.payment_date = payment_date
        if notes is not None:
            payment.notes = notes
        db.commit()
        db.refresh(payment)
    return payment


def get_user_weeks_paid(db: Session, user_id: int) -> list[dict]:
    """Get 52 weeks for a user, marking which are paid.

    Each week costs €1. Payments accumulate and extend the paid period.
    Additionally, all weeks up to the CURRENT week of 2026 are forced to
    'paid' (objective: "colocar todos os utilizadores pagos até à semana corrente").
    Returns a list of 52 week dicts with: week_number, date_start, date_end, paid, month
    """
    from datetime import date, timedelta
    from sqlalchemy import func
    from models.payment import Payment

    MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                   "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    # Get total amount paid by this user
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.user_id == user_id
    ).scalar() or 0.0

    # Each €1 = 1 week paid
    weeks_paid = int(total_paid)

    # Start from the beginning of the current year
    today = date.today()
    year_start = date(today.year, 1, 1)

    # Current week of the year (ISO)
    current_week = int(today.strftime("%V"))

    # Find Monday of week 1
    monday = year_start - timedelta(days=year_start.weekday())

    weeks = []
    for i in range(52):
        week_num = i + 1
        week_start = monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        # Determine the month this week belongs to (by the Wednesday of the week)
        wednesday = week_start + timedelta(days=2)
        month_name = MONTH_NAMES[wednesday.month - 1]
        # Paid if: explicit payment covers it OR it's at/before the current week
        paid = (week_num <= weeks_paid) or (week_num <= current_week)
        weeks.append({
            "week_number": week_num,
            "date_start": week_start.strftime("%d/%m"),
            "date_end": week_end.strftime("%d/%m"),
            "paid": paid,
            "current": week_start <= today <= week_end,
            "month": month_name,
            "month_num": wednesday.month,
        })

    return weeks


def get_all_users_weeks(db: Session) -> list[dict]:
    """Get 52-week payment status for all non-admin users."""
    from models.user import User

    users = db.query(User).filter(User.is_admin == False, User.is_active == True).all()
    result = []
    for user in users:
        weeks = get_user_weeks_paid(db, user.id)
        paid_count = sum(1 for w in weeks if w["paid"])
        result.append({
            "user_id": user.id,
            "username": user.username,
            "weeks": weeks,
            "paid_count": paid_count,
        })
    return result


def get_monthly_payment_totals(db: Session) -> list[dict]:
    """Get total payments grouped by month."""
    results = db.query(
        func.strftime("%Y-%m", Payment.payment_date).label("month"),
        func.sum(Payment.amount).label("total"),
        func.count(Payment.id).label("count")
    ).group_by("month").order_by("month").all()
    return [{"month": r[0], "total": float(r[1]), "count": r[2]} for r in results]


def delete_payment(db: Session, payment_id: int) -> bool:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if payment:
        db.delete(payment)
        db.commit()
        return True
    return False


def get_total_payments_by_user(db: Session) -> list[dict]:
    """Get total payments grouped by user."""
    results = (
        db.query(Payment.user_id, func.sum(Payment.amount).label("total"))
        .group_by(Payment.user_id)
        .order_by(func.sum(Payment.amount).desc())
        .all()
    )
    return [{"user_id": r[0], "total": float(r[1])} for r in results]


# ===== Prize Pool (for "spend prizes" feature) =====

def get_prize_pool(db: Session) -> float:
    """Get the current available prize pool (single-row table)."""
    from models.prize_pool import PrizePool
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    return float(pool.available)


def top_up_prize_pool(db: Session, amount: float) -> float:
    """Add `amount` to the prize pool (e.g. after importing 2026 draws)."""
    from models.prize_pool import PrizePool
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    pool.available = float(pool.available) + float(amount)
    db.commit()
    db.refresh(pool)
    return float(pool.available)


def get_total_society_payouts(db: Session) -> float:
    """Sum of all 'gastar prémios' payouts (notes='Prémio distribuído ...').

    This is the 'prémio utilizado' shown on the home page: the total €1-per-user
    payouts distributed from the prize pool.
    """
    from sqlalchemy import func
    total = db.query(func.sum(Payment.amount)).filter(
        Payment.notes.like("Prémio distribuído%")
    ).scalar() or 0.0
    return round(float(total), 2)


def spend_prizes_on_users(db: Session, payment_date=None) -> dict:
    """Distribute the prize pool as €1 payments to each active non-admin user.

    Spends 1€ per user until the pool is exhausted. Returns a summary dict:
        {"distributed": float, "remaining": float, "users_paid": int, "per_user": float}
    """
    from datetime import date
    from models.prize_pool import PrizePool
    from models.user import User

    if payment_date is None:
        payment_date = date.today()

    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0)
        db.add(pool)
        db.commit()
        db.refresh(pool)

    available = float(pool.available)
    if available <= 0:
        return {"distributed": 0.0, "remaining": 0.0, "users_paid": 0, "per_user": 0.0}

    # Active, non-admin users
    users = db.query(User).filter(User.is_admin == False, User.is_active == True).all()
    if not users:
        return {"distributed": 0.0, "remaining": available, "users_paid": 0, "per_user": 0.0}

    n_users = len(users)
    # Each user gets 1€ while there's enough; remainder stays in pool
    per_user = int(available) // n_users  # whole euros per user
    if per_user < 1:
        # Not enough for a full €1 per user — give 1€ to as many as possible
        users_paid = int(available)
        per_user = 1
    else:
        users_paid = n_users

    distributed = 0.0
    for u in users[:users_paid]:
        create_payment(db, u.id, None, float(per_user), payment_date,
                       "Prémio distribuído (gastar prémios)")
        distributed += float(per_user)

    pool.available = available - distributed
    db.commit()
    db.refresh(pool)

    return {
        "distributed": round(distributed, 2),
        "remaining": round(float(pool.available), 2),
        "users_paid": users_paid,
        "per_user": float(per_user),
    }
