from sqlalchemy import Column, Integer, Float
from database import Base


class PrizePool(Base):
    """Single-row table tracking the available prize pool to be 'spent' on users.

    The pool starts at 0 and is topped up by the total prizes of 2026 draws
    (or manually). The 'spend prizes' action distributes €1 per user until the
    pool is exhausted, and the remainder stays in the pool.
    """
    __tablename__ = "prize_pool"

    id = Column(Integer, primary_key=True, autoincrement=True)
    available = Column(Float, default=0.0, nullable=False)

    def __repr__(self):
        return f"<PrizePool(id={self.id}, available={self.available})>"
