from sqlalchemy import Column, Integer, String, Float, Boolean
from database import Base


class PrizeTier(Base):
    __tablename__ = "prize_tiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier = Column(Integer, unique=True, nullable=False)  # 1-12
    name = Column(String(10), nullable=False)            # e.g. "5+2"
    matched_numbers = Column(Integer, nullable=False)
    matched_stars = Column(Integer, nullable=False)
    prize_amount = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<PrizeTier(tier={self.tier}, name='{self.name}', amount={self.prize_amount})>"
