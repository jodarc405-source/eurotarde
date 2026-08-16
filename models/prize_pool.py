from sqlalchemy import Column, Integer, Float
from database import Base


class PrizePool(Base):
    """Single-row table tracking the available prize pool to be 'spent' on users.

    The pool starts at 0 and is topped up by the total prizes of 2026 draws
    (or manually). The 'spend prizes' action distributes €1 per user until the
    pool is exhausted, and the remainder stays in the pool.

    caixa: tracks a separate box balance. Every prize-winning draw adds 0.26€
    to this box. When 'spend prizes' is used, amounts withdrawn are subtracted
    from this box.
    """
    __tablename__ = "prize_pool"

    id = Column(Integer, primary_key=True, autoincrement=True)
    available = Column(Float, default=0.0, nullable=False)
    caixa = Column(Float, default=0.26, nullable=False)  # Start with 0.26€ as requested

    def __repr__(self):
        return f"<PrizePool(id={self.id}, available={self.available}, caixa={self.caixa})>"
