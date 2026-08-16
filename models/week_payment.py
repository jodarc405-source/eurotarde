from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class WeekPayment(Base):
    """Tracks which weeks a user has paid, and the SOURCE of each paid week.

    source:
      - 'payment'  -> paid via normal quota payment (shown GREEN)
      - 'prize'    -> paid via "gastar prémios" distribution (shown ORANGE)

    A week is considered paid for a user if there is a WeekPayment row for
    (user_id, week_number, year). Weeks up to the CURRENT week are auto-marked
    paid (assumed paid) when no explicit row exists, to keep historical display.
    """

    __tablename__ = "week_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    source = Column(String(20), nullable=False, default="payment")  # 'payment' | 'prize'

    user = relationship("User", back_populates="week_payments")

    def __repr__(self):
        return f"<WeekPayment(user_id={self.user_id}, w={self.week_number}, src={self.source})>"
