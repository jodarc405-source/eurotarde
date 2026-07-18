from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Draw(Base):
    __tablename__ = "draws"

    id = Column(Integer, primary_key=True, autoincrement=True)
    draw_date = Column(Date, unique=True, nullable=False)
    numbers = Column(String(100), nullable=False)  # JSON array of 5 ints
    stars = Column(String(50), nullable=False)     # JSON array of 2 ints
    prize_total = Column(Float, default=0.0)
    is_manual = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # NOTE: cascade="all" (no delete-orphan) — see models/user.py for rationale.
    # This prevents the admin "clear draws" action from orphan-deleting rows.
    keys = relationship("Key", back_populates="draw", cascade="all")
    payments = relationship("Payment", back_populates="draw", cascade="all")

    def __repr__(self):
        return f"<Draw(id={self.id}, date='{self.draw_date}')>"
