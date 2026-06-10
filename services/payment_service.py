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
    """Get 52 weeks for a user, marking which are paid based on total payments.

    Each week costs €1. Payments accumulate and extend the paid period.
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
        weeks.append({
            "week_number": week_num,
            "date_start": week_start.strftime("%d/%m"),
            "date_end": week_end.strftime("%d/%m"),
            "paid": week_num <= weeks_paid,
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
