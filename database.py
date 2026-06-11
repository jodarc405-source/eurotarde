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

        # Seed default prize tiers (upsert — only inserts missing tiers)
        default_tiers = [
            (1, "5+2", 5, 2, 0.0),
            (2, "5+1", 5, 1, 365514.68),
            (3, "5+0", 5, 0, 21356.70),
            (4, "4+2", 4, 2, 2157.43),
            (5, "4+1", 4, 1, 134.16),
            (6, "3+2", 3, 2, 71.27),
            (7, "4+0", 4, 0, 44.13),
            (8, "2+2", 2, 2, 16.27),
            (9, "3+1", 3, 1, 12.06),
            (10, "3+0", 3, 0, 9.16),
            (11, "1+2", 1, 2, 7.80),
            (12, "2+1", 2, 1, 5.67),
            (13, "2+0", 2, 0, 3.72),
        ]
        for tier_num, name, mn, ms, amount in default_tiers:
            existing = db.query(PrizeTier).filter(PrizeTier.tier == tier_num).first()
            if not existing:
                db.add(PrizeTier(tier=tier_num, name=name, matched_numbers=mn, matched_stars=ms, prize_amount=amount))

        db.commit()
    finally:
        db.close()
