import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables, add missing columns, and seed default data."""
    from models import User, PrizeTier
    from services.auth_service import hash_password

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Migration: add 'label' column to keys table if missing
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing_columns = [col["name"] for col in inspector.get_columns("keys")]
    if "label" not in existing_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE keys ADD COLUMN label VARCHAR(100) DEFAULT ''"))
            conn.commit()
        logger.info("Migration: added 'label' column to keys table")

    db = SessionLocal()
    try:
        # Seed admin user if not exists
        admin = db.query(User).filter(User.username == settings.ADMIN_DEFAULT_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.ADMIN_DEFAULT_USERNAME,
                email="admin@eurotarde.local",
                hashed_password=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                is_admin=True,
                is_active=True,
            )
            db.add(admin)

        # Seed default prize tiers if not exist
        if db.query(PrizeTier).count() == 0:
            default_tiers = [
                PrizeTier(tier=1, name="5+2", matched_numbers=5, matched_stars=2, prize_amount=0.0),
                PrizeTier(tier=2, name="5+1", matched_numbers=5, matched_stars=1, prize_amount=125000.0),
                PrizeTier(tier=3, name="5+0", matched_numbers=5, matched_stars=0, prize_amount=25000.0),
                PrizeTier(tier=4, name="4+2", matched_numbers=4, matched_stars=2, prize_amount=1500.0),
                PrizeTier(tier=5, name="4+1", matched_numbers=4, matched_stars=1, prize_amount=100.0),
                PrizeTier(tier=6, name="3+2", matched_numbers=3, matched_stars=2, prize_amount=50.0),
                PrizeTier(tier=7, name="4+0", matched_numbers=4, matched_stars=0, prize_amount=40.0),
                PrizeTier(tier=8, name="2+2", matched_numbers=2, matched_stars=2, prize_amount=12.0),
                PrizeTier(tier=9, name="3+1", matched_numbers=3, matched_stars=1, prize_amount=10.0),
                PrizeTier(tier=10, name="3+0", matched_numbers=3, matched_stars=0, prize_amount=8.0),
                PrizeTier(tier=11, name="1+2", matched_numbers=1, matched_stars=2, prize_amount=6.0),
                PrizeTier(tier=12, name="2+1", matched_numbers=2, matched_stars=1, prize_amount=5.0),
            ]
            db.add_all(default_tiers)

        db.commit()
    finally:
        db.close()
