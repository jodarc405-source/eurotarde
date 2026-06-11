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
    prize = determine_prize(mn, ms, tiers, draw.prize_total)

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


def check_my_key_against_all_draws(db: Session, key_id: int) -> list[dict]:
    """Check a specific my_key against ALL draws. Returns list of results with prizes."""
    draws = db.query(Draw).order_by(Draw.draw_date.desc()).all()
    results = []
    for draw in draws:
        result = check_my_key_against_draw(db, key_id, draw.id)
        if "error" not in result and result["prize"] > 0:
            results.append(result)
    return results


def get_all_my_keys_results(db: Session, user_id: int = 0) -> dict:
    """Get all results for all my_keys against all draws. Returns {key_id: [results]}."""
    my_keys = get_my_keys(db, user_id=user_id)
    all_results = {}
    for key in my_keys:
        results = check_my_key_against_all_draws(db, key.id)
        all_results[key.id] = {
            "key": key,
            "wins": results,
            "total_prize": sum(r["prize"] for r in results),
        }
    return all_results
