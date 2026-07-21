"""Pytest configuration for Eurotarde.

Forces a single isolated SQLite database for the whole test session BEFORE any
application module is imported. Without this, each test module sets its own
DATABASE_URL at import time, but `database.py` builds the SQLAlchemy engine only
once (module import) — so every test module in a run ends up sharing whatever DB
the first-imported module pointed at, causing cross-test contamination
(duplicate admin inserts, leftover users/keys). Centralising the DB URL here makes
all tests in a session share one fresh temp DB, which `init_db()` seeds once.
"""
import os
import tempfile


def _setup_test_db():
    if "DATABASE_URL" not in os.environ:
        db_path = tempfile.mktemp(suffix=".db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("***REDACTED***", "test-secret-key-eurotarde")
    os.environ.setdefault("ADMIN_DEFAULT_USERNAME", "admin")
    os.environ.setdefault("ADMIN_DEFAULT_PASSWORD", "admin123")


_setup_test_db()
