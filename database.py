import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args["check_same_thread"] = False
elif "postgresql" in settings.DATABASE_URL:
    connect_args["sslmode"] = "require"

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
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

    # Migration: make payments.draw_id nullable (was NOT NULL, need NULL for quota payments)
    payments_cols = [col["name"] for col in inspector.get_columns("payments")]
    if "draw_id" in payments_cols:
        # Check if draw_id is NOT NULL by trying to insert NULL — recreate table if needed
        # SQLite doesn't support ALTER COLUMN, so we use table recreation
        with engine.connect() as conn:
            # Check current schema
            result = conn.execute(text("PRAGMA table_info(payments)")).fetchall()
            for col in result:
                if col[1] == "draw_id" and col[3] == 1:  # notnull=1 means NOT NULL
                    logger.info("Migration: making payments.draw_id nullable...")
                    # Recreate payments table with nullable draw_id
                    conn.execute(text("""
                        CREATE TABLE IF NOT EXISTS payments_new (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            draw_id INTEGER REFERENCES draws(id),
                            amount FLOAT NOT NULL,
                            payment_date DATE NOT NULL,
                            notes VARCHAR(500),
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("""
                        INSERT INTO payments_new (id, user_id, draw_id, amount, payment_date, notes, created_at, updated_at)
                        SELECT id, user_id, draw_id, amount, payment_date, notes, created_at, updated_at FROM payments
                    """))
                    conn.execute(text("DROP TABLE payments"))
                    conn.execute(text("ALTER TABLE payments_new RENAME TO payments"))
                    conn.commit()
                    logger.info("Migration: payments.draw_id is now nullable")
                    break

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
                PrizeTier(tier=2, name="5+1", matched_numbers=5, matched_stars=1, prize_amount=365514.68),
                PrizeTier(tier=3, name="5+0", matched_numbers=5, matched_stars=0, prize_amount=21356.70),
                PrizeTier(tier=4, name="4+2", matched_numbers=4, matched_stars=2, prize_amount=2157.43),
                PrizeTier(tier=5, name="4+1", matched_numbers=4, matched_stars=1, prize_amount=134.16),
                PrizeTier(tier=6, name="3+2", matched_numbers=3, matched_stars=2, prize_amount=71.27),
                PrizeTier(tier=7, name="4+0", matched_numbers=4, matched_stars=0, prize_amount=44.13),
                PrizeTier(tier=8, name="2+2", matched_numbers=2, matched_stars=2, prize_amount=16.27),
                PrizeTier(tier=9, name="3+1", matched_numbers=3, matched_stars=1, prize_amount=12.06),
                PrizeTier(tier=10, name="3+0", matched_numbers=3, matched_stars=0, prize_amount=9.16),
                PrizeTier(tier=11, name="1+2", matched_numbers=1, matched_stars=2, prize_amount=7.80),
                PrizeTier(tier=12, name="2+1", matched_numbers=2, matched_stars=1, prize_amount=5.67),
                PrizeTier(tier=13, name="2+0", matched_numbers=2, matched_stars=0, prize_amount=3.72),
            ]
            db.add_all(default_tiers)

        db.commit()
    finally:
        db.close()
