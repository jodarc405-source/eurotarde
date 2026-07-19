import json
from sqlalchemy.orm import Session
from models.key import Key
from models.draw import Draw
from models.prize import PrizeTier


def check_key_against_draw(numbers: list[int], stars: list[int],
                           draw_numbers: list[int], draw_stars: list[int]) -> tuple[int, int]:
    """Check a key against a draw. Returns (matched_numbers, matched_stars)."""
    matched_numbers = len(set(numbers) & set(draw_numbers))
    matched_stars = len(set(stars) & set(draw_stars))
    return matched_numbers, matched_stars


def determine_prize(matched_numbers: int, matched_stars: int,
                    prize_tiers: list[PrizeTier], jackpot_total: float = 0.0,
                    draw_id: int = None, db=None) -> float:
    """Determine prize amount based on matches.

    Uses the REAL per-draw prize breakdown (DrawPrize) when available —
    Euromillions prizes vary every draw, so the static prize_tiers table is
    only a fallback. The 5+2 jackpot always comes from `jackpot_total`.
    """
    # Special case: 5+2 wins the jackpot
    if matched_numbers == 5 and matched_stars == 2:
        return jackpot_total

    # Prefer the real per-draw amounts (Portugal breakdown)
    if draw_id is not None and db is not None:
        from services.prize_service import prize_for_tier
        real = prize_for_tier(db, draw_id, matched_numbers, matched_stars)
        if real is not None:
            return real

    # Fallback to the static prize tiers table
    for tier in prize_tiers:
        if tier.matched_numbers == matched_numbers and tier.matched_stars == matched_stars:
            return tier.prize_amount
    return 0.0


def check_user_keys_for_draw(db: Session, user_id: int, draw_id: int) -> list[Key]:
    """Check all of a user's keys for a specific draw. Returns updated keys."""
    draw = db.query(Draw).filter(Draw.id == draw_id).first()
    if not draw:
        return []

    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)
    prize_tiers = db.query(PrizeTier).filter(PrizeTier.is_active == True).all()

    keys = db.query(Key).filter(Key.user_id == user_id, Key.draw_id == draw_id).all()

    for key in keys:
        key_numbers = json.loads(key.numbers)
        key_stars = json.loads(key.stars)

        matched_numbers, matched_stars = check_key_against_draw(
            key_numbers, key_stars, draw_numbers, draw_stars
        )

        key.matched_numbers = matched_numbers
        key.matched_stars = matched_stars
        key.prize_won = determine_prize(matched_numbers, matched_stars, prize_tiers, draw.prize_total, draw_id=draw.id, db=db)

    db.commit()
    return keys


def create_key_for_user(db: Session, user_id: int, draw_id: int,
                        numbers: list[int], stars: list[int]) -> Key:
    """Create a new key for a user and draw."""
    key = Key(
        user_id=user_id,
        draw_id=draw_id,
        numbers=json.dumps(sorted(numbers)),
        stars=json.dumps(sorted(stars)),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def get_user_keys(db: Session, user_id: int, draw_id: int = None) -> list[Key]:
    """Get all keys for a user, optionally filtered by draw."""
    query = db.query(Key).filter(Key.user_id == user_id)
    if draw_id:
        query = query.filter(Key.draw_id == draw_id)
    return query.order_by(Key.created_at.desc()).all()


def get_all_keys_for_draw(db: Session, draw_id: int) -> list[Key]:
    """Get all keys for a specific draw."""
    return db.query(Key).filter(Key.draw_id == draw_id).all()
