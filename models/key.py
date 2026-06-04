from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Key(Base):
    __tablename__ = "keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    draw_id = Column(Integer, ForeignKey("draws.id"), nullable=False)
    numbers = Column(String(100), nullable=False)  # JSON array of 5 ints
    stars = Column(String(50), nullable=False)     # JSON array of 2 ints
    matched_numbers = Column(Integer, default=0)
    matched_stars = Column(Integer, default=0)
    prize_won = Column(Float, default=0.0)
    label = Column(String(100), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="keys")
    draw = relationship("Draw", back_populates="keys")

    def __repr__(self):
        return f"<Key(id={self.id}, user_id={self.user_id}, draw_id={self.draw_id}, prize={self.prize_won})>"
