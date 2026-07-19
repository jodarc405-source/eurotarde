import json
from datetime import date
from sqlalchemy.orm import Session
from models.key import Key
from models.draw import Draw
from models.prize import PrizeTier
from services.key_checker import check_key_against_draw, determine_prize


def create_my_key(db: Session, numbers: list[int], stars: list[int], label: str = "", user_id: int = 0) -> Key:
    """Create a new 'my key' — a persistent key that gets checked against all draws."""
    key = Key(
        user_id=user_id,
        draw_id=0,  # 0 = not tied to a specific draw
        numbers=json.dumps(sorted(numbers)),
        stars=json.dumps(sorted(stars)),
        label=label,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def get_my_keys(db: Session, user_id: int = 0) -> list[Key]:
    """Get all 'my keys' for a given user (default 0 = system keys)."""
    return db.query(Key).filter(Key.user_id == user_id).order_by(Key.created_at.desc()).all()


def get_my_key_by_id(db: Session, key_id: int, user_id: int = 0) -> Key | None:
    return db.query(Key).filter(Key.id == key_id, Key.user_id == user_id).first()


def delete_my_key(db: Session, key_id: int, user_id: int = 0) -> bool:
    key = db.query(Key).filter(Key.id == key_id, Key.user_id == user_id).first()
    if key:
        db.delete(key)
        db.commit()
        return True
    return False


def check_my_key_against_draw(db: Session, key_id: int, draw_id: int, user_id: int = 0) -> dict:
    """Check a specific my_key against a specific draw. Returns result dict."""
    key = db.query(Key).filter(Key.id == key_id, Key.user_id == user_id).first()
    draw = db.query(Draw).filter(Draw.id == draw_id).first()
    if not key or not draw:
        return {"error": "Key or draw not found"}

    key_numbers = json.loads(key.numbers)
    key_stars = json.loads(key.stars)
    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)

    mn, ms = check_key_against_draw(key_numbers, key_stars, draw_numbers, draw_stars)
    tiers = db.query(PrizeTier).filter(PrizeTier.is_active == True).all()
    prize = determine_prize(mn, ms, tiers, draw.prize_total, draw_id=draw.id, db=db)

    return {
        "key_id": key_id,
        "draw_id": draw_id,
        "draw_date": draw.draw_date.isoformat(),
        "key_numbers": key_numbers,
        "key_stars": key_stars,
        "draw_numbers": draw_numbers,
        "draw_stars": draw_stars,
        "matched_numbers": mn,
        "matched_stars": ms,
        "prize": prize,
        "label": getattr(key, 'label', ''),
    }


def check_all_my_keys_against_draw(db: Session, draw_id: int, user_id: int = 0) -> list[dict]:
    """Check all my_keys against a specific draw. Returns list of results."""
    my_keys = get_my_keys(db, user_id=user_id)
    results = []
    for key in my_keys:
        result = check_my_key_against_draw(db, key.id, draw_id, user_id=user_id)
        if "error" not in result:
            results.append(result)
    return results


def check_my_key_against_all_draws(db: Session, key_id: int, user_id: int = 0) -> list[dict]:
    """Check a specific my_key against ALL draws. Returns list of results with prizes."""
    draws = db.query(Draw).order_by(Draw.draw_date.desc()).all()
    results = []
    for draw in draws:
        result = check_my_key_against_draw(db, key_id, draw.id, user_id=user_id)
        if "error" not in result and result["prize"] > 0:
            results.append(result)
    return results


def get_all_my_keys_results(db: Session, user_id: int = 0) -> dict:
    """Get all results for all my_keys against all draws. Returns {key_id: [results]}."""
    my_keys = get_my_keys(db, user_id=user_id)
    all_results = {}
    for key in my_keys:
        results = check_my_key_against_all_draws(db, key.id, user_id=user_id)
        all_results[key.id] = {
            "key": key,
            "wins": results,
            "total_prize": sum(r["prize"] for r in results),
        }
    return all_results


def get_distinct_user_ids_with_keys(db: Session) -> list[int]:
    """Return all distinct user_ids that own at least one 'my key'."""
    return [row[0] for row in db.query(Key.user_id)
            .filter(Key.user_id != 0)
            .distinct()
            .all()]


def update_prizes_for_all_users(db: Session) -> dict:
    """Recompute prizes for each user's 'my keys' against every draw.

    Returns a summary dict {user_id: total_prize}. Used after a new draw is
    imported so every user's stored/dashboard prize figures stay current.
    """
    summary = {}
    user_ids = get_distinct_user_ids_with_keys(db)
    for uid in user_ids:
        total = 0.0
        my_keys = get_my_keys(db, user_id=uid)
        for key in my_keys:
            results = check_my_key_against_all_draws(db, key.id, user_id=uid)
            total += sum(r["prize"] for r in results)
        summary[uid] = round(total, 2)
    return summary


# ===== Society key (shared by all users, created by admin) =====

def create_society_key(db: Session, numbers: list[int], stars: list[int], label: str = "Chave da Sociedade") -> Key:
    """Create (or replace) the society key — one shared key for all users.

    There can be only one active society key: if one exists, it is deleted
    and a new one created (so the society key is always unique).
    """
    existing = get_society_key(db)
    if existing:
        db.delete(existing)
        db.commit()
    key = Key(
        user_id=0,  # system / society
        draw_id=0,
        numbers=json.dumps(sorted(numbers)),
        stars=json.dumps(sorted(stars)),
        label=label,
        is_society=True,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def get_society_key(db: Session) -> Key | None:
    """Return the active society key (is_society=True), or None."""
    return db.query(Key).filter(Key.is_society == True).order_by(Key.id.desc()).first()


def get_society_key_results(db: Session) -> dict:
    """Get results of the society key against all draws. Returns {key_id: [results]}."""
    society_key = get_society_key(db)
    if not society_key:
        return {}
    results = check_my_key_against_all_draws(db, society_key.id, user_id=0)
    return {
        society_key.id: {
            "key": society_key,
            "wins": results,
            "total_prize": sum(r["prize"] for r in results),
        }
    }


def get_society_prizes_2026(db: Session) -> float:
    """Sum of prizes won by the society key across all 2026 draws."""
    from datetime import date as d
    society_key = get_society_key(db)
    if not society_key:
        return 0.0
    results = check_my_key_against_all_draws(db, society_key.id, user_id=0)
    year_start = d(2026, 1, 1)
    year_end = d(2026, 12, 31)
    total = 0.0
    for r in results:
        draw_date = d.fromisoformat(r["draw_date"])
        if year_start <= draw_date <= year_end:
            total += r["prize"]
    return round(total, 2)


def get_society_key_results_2026(db: Session) -> dict:
    """Like get_society_key_results, but restricted to 2026 draws only.

    Returns {key_id: {"key":..., "wins": [2026 results], "total_prize": sum}}.
    This keeps the home-page 'Total Ganho' card consistent with the
    'Prémios 2026' stat card (both reflect 2026 only).
    """
    society_key = get_society_key(db)
    if not society_key:
        return {}
    from datetime import date as d
    all_results = check_my_key_against_all_draws(db, society_key.id, user_id=0)
    year_start = d(2026, 1, 1)
    year_end = d(2026, 12, 31)
    wins_2026 = [
        r for r in all_results
        if year_start <= d.fromisoformat(r["draw_date"]) <= year_end
    ]
    return {
        society_key.id: {
            "key": society_key,
            "wins": wins_2026,
            "total_prize": round(sum(r["prize"] for r in wins_2026), 2),
        }
    }


def check_society_key_against_draw(db: Session, draw_id: int) -> list[dict]:
    """Check ONLY the society key against a specific draw.

    Unlike check_all_my_keys_against_draw(db, draw_id, user_id=0) — which
    picks up EVERY key with user_id=0 (including test/seed keys) — this
    uses just the single active society key, so prizes are never double-counted.
    """
    society_key = get_society_key(db)
    if not society_key:
        return []
    result = check_my_key_against_draw(db, society_key.id, draw_id, user_id=0)
    if "error" not in result:
        return [result]
    return []
