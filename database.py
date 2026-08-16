import json
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Normalize the DB URL so SQLAlchemy uses the right driver AND is robust to
# whitespace/newlines that can sneak in when the value is pasted into the
# Render dashboard (e.g. a line break splitting "5432" into "54\n32").
# Strip every whitespace char, then rewrite the scheme to force psycopg v3.
db_url = settings.DATABASE_URL
if db_url:
    db_url = "".join(db_url.split())  # remove all whitespace/newlines
if db_url.startswith("postgresql+psycopg2://"):
    db_url = "postgresql+psycopg://" + db_url[len("postgresql+psycopg2://"):]
elif db_url.startswith("postgresql://"):
    db_url = "postgresql+psycopg://" + db_url[len("postgresql://"):]

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif "postgresql" in db_url:
    connect_args["sslmode"] = "require"

engine = create_engine(
    db_url,
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

    # Migration: add 'is_society' column to keys table if missing
    keys_cols = [col["name"] for col in inspector.get_columns("keys")]
    if "is_society" not in keys_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE keys ADD COLUMN is_society BOOLEAN DEFAULT 0"))
            conn.commit()
        logger.info("Migration: added 'is_society' column to keys table")

    # Migration: make keys.user_id nullable (society/system keys have no owner).
    # PostgreSQL enforces FK constraints, so user_id=0/None must be allowed.
    if "postgresql" in db_url:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE keys ALTER COLUMN user_id DROP NOT NULL"))
            conn.execute(text("ALTER TABLE keys ALTER COLUMN draw_id DROP NOT NULL"))
            conn.commit()
        logger.info("Migration: keys.user_id/draw_id are now nullable (PostgreSQL)")

    # Migration: make payments.draw_id nullable (was NOT NULL, need NULL for quota payments)
    # NOTE: This is SQLite-specific. PostgreSQL handles nullable columns differently,
    # so we skip it on non-SQLite backends to avoid breaking init_db() in production.
    payments_cols = [col["name"] for col in inspector.get_columns("payments")]
    if "draw_id" in payments_cols:
        try:
            with engine.connect() as conn:
                # Check current schema (SQLite only — PRAGMA is not portable)
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
        except Exception as e:
            # PostgreSQL or other backend: PRAGMA not supported, column likely already nullable
            logger.warning(f"Skipping SQLite-specific payments migration on this backend: {e}")

    # Migration: create draw_prizes table if missing (real per-draw prize amounts)
    from sqlalchemy import inspect as _inspect
    inspector2 = _inspect(engine)
    if "draw_prizes" not in inspector2.get_table_names():
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["draw_prizes"]])
        logger.info("Migration: created draw_prizes table")

    # Migration: create week_payments table if missing (paid-week tracking + source color)
    if "week_payments" not in inspector2.get_table_names():
        Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["week_payments"]])
        logger.info("Migration: created week_payments table")

    # Migration: add 'caixa' column to prize_pool table if missing (added 2026-08-16)
    if "prize_pool" in inspector2.get_table_names():
        prize_pool_cols = [col["name"] for col in inspector2.get_columns("prize_pool")]
        if "caixa" not in prize_pool_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE prize_pool ADD COLUMN caixa FLOAT DEFAULT 0.26 NOT NULL"))
                conn.commit()
            logger.info("Migration: added 'caixa' column to prize_pool table")

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