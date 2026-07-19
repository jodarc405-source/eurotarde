from sqlalchemy import Column, Integer, String, Float, ForeignKey
from database import Base


class DrawPrize(Base):
    """Real prize-per-winner amount for each tier of a specific draw.

    Euromillions prizes vary every draw (the jackpot rolls, and the lower
    tiers are split by the number of winners). The static prize_tiers table
    is only a fallback; the authoritative values come from the official
    'Prize Breakdown' page for each draw (section #PrizePT).
    """

    __tablename__ = "draw_prizes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    draw_id = Column(Integer, ForeignKey("draws.id"), nullable=False, unique=True)
    # Prize per winner for each of the 13 tiers, keyed by "M+S" (e.g. "5+2").
    # Stored as a JSON object: {"5+2": 49675416.9, "5+1": 0.0, ...}
    prizes = Column(String(2000), nullable=False, default="{}")

    def __repr__(self):
        return f"<DrawPrize(draw_id={self.draw_id})>"
