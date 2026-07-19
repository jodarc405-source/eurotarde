"""Per-draw prize amounts (real values fetched from the official breakdown)."""

import json
from sqlalchemy.orm import Session
from models.draw_prize import DrawPrize


def save_draw_prizes(db: Session, draw_id: int, prizes: dict[str, float]) -> DrawPrize:
    """Store (upsert) the Portugal prize-per-winner breakdown for a draw.

    `prizes` is keyed by "M+S" (e.g. "5+2") -> amount (float).
    """
    existing = db.query(DrawPrize).filter(DrawPrize.draw_id == draw_id).first()
    payload = json.dumps(prizes, ensure_ascii=False)
    if existing:
        existing.prizes = payload
        db.commit()
        db.refresh(existing)
        return existing
    row = DrawPrize(draw_id=draw_id, prizes=payload)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_draw_prizes(db: Session, draw_id: int) -> dict[str, float]:
    """Return the Portugal prize-per-winner breakdown for a draw, as a dict.

    Falls back to {} when no real breakdown is stored.
    """
    row = db.query(DrawPrize).filter(DrawPrize.draw_id == draw_id).first()
    if not row:
        return {}
    try:
        return json.loads(row.prizes)
    except (ValueError, TypeError):
        return {}


def prize_for_tier(db: Session, draw_id: int, matched_numbers: int,
                   matched_stars: int) -> float | None:
    """Return the real prize amount for a given match tier in a specific draw.

    Returns None when no breakdown is stored (caller should fall back to the
    static prize_tiers table).
    """
    prizes = get_draw_prizes(db, draw_id)
    if not prizes:
        return None
    key = f"{matched_numbers}+{matched_stars}"
    return prizes.get(key)
