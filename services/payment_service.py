from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.payment import Payment


def create_payment(db: Session, user_id: int, draw_id: int | None, amount: float, payment_date: date, notes: str | None = None) -> Payment:
    from config import get_settings
    from models.week_payment import WeekPayment
    
    settings = get_settings()
    week_value = getattr(settings, 'WEEK_VALUE', 1.0)
    
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
    
    # If this is a regular payment (not from "gastar prémios"), add green weeks
    # Only for payments without "Prémio distribuído" in notes
    if notes is None or "Prémio distribuído" not in notes:
        # Calculate how many whole weeks this payment covers
        weeks = int(amount // week_value)
        if weeks > 0:
            # Get current paid weeks for this user/year
            year = payment_date.year
            paid_weeks = db.query(WeekPayment.week_number).filter(
                WeekPayment.user_id == user_id,
                WeekPayment.year == year
            ).all()
            paid_week_nums = {w[0] for w in paid_weeks}
            
            # Find next unpaid weeks
            next_weeks = []
            for w in range(1, 53):
                if w not in paid_week_nums and len(next_weeks) < weeks:
                    next_weeks.append(w)
            
            # Add WeekPayment entries with source='payment' (green)
            for week_num in next_weeks:
                wp = WeekPayment(
                    user_id=user_id,
                    week_number=week_num,
                    year=year,
                    source="payment"
                )
                db.add(wp)
            
            db.commit()
    
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


def get_user_weeks_paid(db: Session, user_id: int, year: int | None = None) -> list[dict]:
    """Get 52 weeks for a user, with per-week paid status AND source color.

    Sources of "paid":
      - Weeks up to the CURRENT week are auto-marked paid (green) — the user is
        assumed to be up to date.
      - Explicit WeekPayment rows (from payments or "gastar prémios") set the
        exact week + source ('payment' = green, 'prize' = orange).

    Returns a list of 52 week dicts with: week_number, date_start, date_end,
    paid (bool), source ('payment'|'prize'|None), current, month, month_num.
    """
    from datetime import date, timedelta
    from models.week_payment import WeekPayment

    if year is None:
        year = date.today().year

    MONTH_NAMES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                   "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    # Explicit paid weeks from the week_payments table
    rows = db.query(WeekPayment).filter(
        WeekPayment.user_id == user_id,
        WeekPayment.year == year,
    ).all()
    paid_map = {r.week_number: r.source for r in rows}

    today = date.today()
    year_start = date(year, 1, 1)
    current_week = int(today.strftime("%V"))
    monday = year_start - timedelta(days=year_start.weekday())

    weeks = []
    for i in range(52):
        week_num = i + 1
        week_start = monday + timedelta(weeks=i)
        week_end = week_start + timedelta(days=6)
        wednesday = week_start + timedelta(days=2)
        month_name = MONTH_NAMES[wednesday.month - 1]
        # Only explicit WeekPayment rows mark a week paid (green/prize).
        # No auto "up to current week" — every paid week is stored explicitly.
        if week_num in paid_map:
            paid = True
            source = paid_map[week_num]
        else:
            paid = False
            source = None
        is_current = week_start <= today <= week_end
        # current week gets a subtle highlight even if unpaid
        cls_current = is_current
        weeks.append({
            "week_number": week_num,
            "date_start": week_start.strftime("%d/%m"),
            "date_end": week_end.strftime("%d/%m"),
            "paid": paid,
            "source": source,
            "current": cls_current,
            "month": month_name,
            "month_num": wednesday.month,
        })

    return weeks


def set_user_weeks_source(db: Session, user_id: int, start_week: int, count: int,
                          source: str, year: int | None = None) -> int:
    """Mark `count` weeks starting at `start_week` for a user with a given source.

    Returns the number of weeks actually written. Conflicts (a week already
    marked) keep the existing source unless it was the auto 'current-week' green.
    """
    from models.week_payment import WeekPayment
    if year is None:
        from datetime import date
        year = date.today().year
    written = 0
    for w in range(start_week, start_week + count):
        if w < 1 or w > 52:
            continue
        existing = db.query(WeekPayment).filter(
            WeekPayment.user_id == user_id,
            WeekPayment.week_number == w,
            WeekPayment.year == year,
        ).first()
        if existing:
            # Override only if not already explicitly set (avoid clobbering)
            if existing.source != source:
                existing.source = source
                written += 1
        else:
            db.add(WeekPayment(user_id=user_id, week_number=w, year=year, source=source))
            written += 1
    db.commit()
    return written


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


def get_caixa(db: Session) -> float:
    """Get the current caixa balance (single-row table)."""
    from models.prize_pool import PrizePool
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0, caixa=0.26)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    return float(pool.caixa)


def add_to_caixa(db: Session, amount: float) -> float:
    """Add `amount` to the caixa balance."""
    from models.prize_pool import PrizePool
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0, caixa=0.26)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    pool.caixa = float(pool.caixa) + float(amount)
    db.commit()
    db.refresh(pool)
    return float(pool.caixa)


def subtract_from_caixa(db: Session, amount: float) -> float:
    """Subtract `amount` from the caixa balance."""
    from models.prize_pool import PrizePool
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0, caixa=0.26)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    pool.caixa = max(0.0, float(pool.caixa) - float(amount))
    db.commit()
    db.refresh(pool)
    return float(pool.caixa)


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


def spend_prizes_on_users(db: Session, payment_date=None, user_amounts=None) -> dict:
    """Distribute the caixa balance as payments to selected users (gastar prémios).
    
    Args:
        db: Database session
        payment_date: Date for the payment (default: today)
        user_amounts: Dict {user_id: amount} specifying how much to spend per user.
                      If None, falls back to old behavior (€1 per user from prize pool).
    
    Returns a summary dict:
        {"distributed": float, "remaining_caixa": float, "users_paid": int, "weeks_added": int}
    """
    from datetime import date
    from models.prize_pool import PrizePool
    from models.user import User
    from models.week_payment import WeekPayment
    from config import get_settings
    
    settings = get_settings()
    week_value = getattr(settings, 'WEEK_VALUE', 1.0)
    
    if payment_date is None:
        payment_date = date.today()
    
    pool = db.query(PrizePool).order_by(PrizePool.id).first()
    if pool is None:
        pool = PrizePool(available=0.0, caixa=0.26)
        db.add(pool)
        db.commit()
        db.refresh(pool)
    
    # If user_amounts provided, use caixa; otherwise fall back to old behavior
    if user_amounts is not None:
        # New behavior: use caixa balance
        available_caixa = float(pool.caixa)
        if available_caixa <= 0:
            return {"distributed": 0.0, "remaining_caixa": 0.0, "users_paid": 0, "weeks_added": 0}
        
        # Validate user amounts and check against caixa balance
        total_requested = sum(user_amounts.values())
        if total_requested > available_caixa:
            # Not enough in caixa - scale down proportionally or reject
            # We'll reject and let the UI handle it
            return {"distributed": 0.0, "remaining_caixa": available_caixa, "users_paid": 0, "weeks_added": 0, "error": "Saldo insuficiente na Caixa"}
        
        # Get active non-admin users that have amounts specified
        user_ids = list(user_amounts.keys())
        users = db.query(User).filter(
            User.id.in_(user_ids),
            User.is_admin == False,
            User.is_active == True
        ).all()
        
        if not users:
            return {"distributed": 0.0, "remaining_caixa": available_caixa, "users_paid": 0, "weeks_added": 0}
        
        distributed = 0.0
        weeks_added = 0
        
        for user in users:
            amount = user_amounts.get(user.id, 0)
            if amount <= 0:
                continue
            
            # Create payment record
            create_payment(db, user.id, None, amount, payment_date,
                          "Prémio distribuído (gastar prémios)")
            
            # Calculate how many weeks this covers (whole weeks only)
            weeks = int(amount // week_value)
            if weeks > 0:
                # Find the next unpaid weeks for this user and mark them as 'prize' (orange)
                # Get current paid weeks
                paid_weeks = db.query(WeekPayment.week_number).filter(
                    WeekPayment.user_id == user.id,
                    WeekPayment.year == payment_date.year
                ).all()
                paid_week_nums = {w[0] for w in paid_weeks}
                
                # Find next unpaid weeks
                next_weeks = []
                for w in range(1, 53):
                    if w not in paid_week_nums and len(next_weeks) < weeks:
                        next_weeks.append(w)
                
                # Add WeekPayment entries with source='prize' (orange)
                for week_num in next_weeks:
                    wp = WeekPayment(
                        user_id=user.id,
                        week_number=week_num,
                        year=payment_date.year,
                        source="prize"
                    )
                    db.add(wp)
                    weeks_added += 1
            
            distributed += amount
        
        # Subtract from caixa
        pool.caixa = max(0.0, float(pool.caixa) - distributed)
        db.commit()
        db.refresh(pool)
        
        return {
            "distributed": round(distributed, 2),
            "remaining_caixa": round(float(pool.caixa), 2),
            "users_paid": len([u for u in users if user_amounts.get(u.id, 0) > 0]),
            "weeks_added": weeks_added,
        }
    
    # Old behavior (fallback): distribute from prize pool, €1 per user
    available = float(pool.available)
    if available <= 0:
        return {"distributed": 0.0, "remaining_caixa": float(pool.caixa), "users_paid": 0, "weeks_added": 0}
    
    # Active, non-admin users
    users = db.query(User).filter(User.is_admin == False, User.is_active == True).all()
    if not users:
        return {"distributed": 0.0, "remaining_caixa": float(pool.caixa), "users_paid": 0, "weeks_added": 0}
    
    n_users = len(users)
    per_user = int(available) // n_users  # whole euros per user
    if per_user < 1:
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
        "remaining_caixa": round(float(pool.caixa), 2),
        "users_paid": users_paid,
        "weeks_added": 0,
    }
