from sqlalchemy import Column, Integer, String, DateTime, Date, func
from database import Base


class PageView(Base):
    __tablename__ = "page_views"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False, default="GET")
    status_code = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    view_date = Column(Date, nullable=False, server_default=func.current_date())
