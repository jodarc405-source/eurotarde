from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # NOTE: use cascade="all" (NOT "delete-orphan"). "delete-orphan" silently
    # deletes child rows whenever the parent's collection is loaded and a child
    # is not present in that in-memory collection — a known hazard that caused
    # users' saved keys to disappear. cascade="all" still deletes children when
    # the parent (user) is deleted, without the orphan-deletion risk.
    keys = relationship("Key", back_populates="user", cascade="all")
    payments = relationship("Payment", back_populates="user", cascade="all")
    week_payments = relationship("WeekPayment", back_populates="user", cascade="all")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', is_admin={self.is_admin})>"
