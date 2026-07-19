"""Automated tests for Eurotarde society-key persistence & prize updates.

Run:  uv run python -m pytest tests/test_persistence.py -q
(or): uv run python tests/test_persistence.py

NOTE: The architecture is a SINGLE shared "Chave da Sociedade" (Key.is_society=True,
user_id=0). There are no per-user keys anymore. These tests assert the society key
persists across logout/login and that prizes are computed against it.
"""
import os
import sys
import tempfile

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use an isolated DB before importing the app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
DB_PATH = _tmp.name
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from database import Base, engine, SessionLocal  # noqa: E402
from models.key import Key  # noqa: E402
from models.draw import Draw  # noqa: E402
from models.user import User  # noqa: E402
from services.draw_service import create_draw  # noqa: E402
from services.my_keys_service import (  # noqa: E402
    check_society_key_against_draw,
    get_society_key,
    get_society_prizes_2026,
)
from datetime import date  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(main.app)


def _count_society_keys():
    db = SessionLocal()
    n = db.query(Key).filter(Key.is_society == True).count()
    db.close()
    return n


def test_society_key_survives_logout_login_cycle():
    """Regression test: the society key must persist across logout+login.

    Mirrors the user's real scenario: they create the Chave da Sociedade, leave
    the site, come back, and it must still be there (not 'undefined')."""
    client.post("/auth/register", data={
        "username": "dave", "email": "dave@x.com",
        "password": "secret123", "confirm_password": "secret123",
    })
    client.post("/auth/login", data={"username": "dave", "password": "secret123"})
    client.post("/sorteios/my-keys/create", data={
        "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
        "s1": 1, "s2": 2, "label": "Chave da Sociedade",
    })
    # fresh client == new session == re-login after logout/restart
    c2 = TestClient(main.app)
    c2.post("/auth/login", data={"username": "dave", "password": "secret123"})
    r = c2.get("/sorteios/my-keys")
    assert "Chave da Sociedade" in r.text, "Society key disappeared after re-login!"
    # and it must be in the DB, not just shown
    assert _count_society_keys() == 1, "Society key row missing from DB after re-login!"


def test_society_key_prizes_after_draw():
    """The society key's prize must be computed when a matching draw arrives."""
    client.post("/auth/register", data={
        "username": "erin", "email": "erin@x.com",
        "password": "secret123", "confirm_password": "secret123",
    })
    client.post("/auth/login", data={"username": "erin", "password": "secret123"})
    client.post("/sorteios/my-keys/create", data={
        "n1": 10, "n2": 20, "n3": 30, "n4": 40, "n5": 50,
        "s1": 11, "s2": 12, "label": "Chave da Sociedade",
    })
    db = SessionLocal()
    society = get_society_key(db)
    # create a draw that matches exactly (5+2 jackpot)
    draw = create_draw(db, date(2031, 5, 5),
                       [10, 20, 30, 40, 50], [11, 12],
                       prize_total=100000000.0, is_manual=True)
    wins = check_society_key_against_draw(db, draw.id)
    db.close()

    assert len(wins) >= 1, "No win recorded for society key!"
    assert wins[0]["prize"] > 0, "Prize not computed for society key!"

    # get_society_prizes_2026 only counts draws in 2026, so check via results
    db = SessionLocal()
    society = get_society_key(db)
    total = get_society_prizes_2026(db)
    db.close()
    assert society is not None, "Society key vanished from DB!"


def test_anonymous_cannot_access_my_keys():
    """Unauthenticated requests to my-keys must be redirected to login,
    preventing silent save/read under user_id=0."""
    c = TestClient(main.app)
    # follow_redirects=False so we see the actual 302 (not the 200 after redirect)
    r = c.get("/sorteios/my-keys", follow_redirects=False)
    assert r.status_code in (302, 307), "Anonymous access to my-keys not blocked!"
    assert "/auth/login" in r.headers.get("location", ""), "Not redirected to login!"


def test_deleting_a_draw_does_not_delete_society_key():
    """Admin 'clear draws' must NOT delete the society key (draw_id=0)."""
    db = SessionLocal()
    before = _count_society_keys()
    # delete a draw (the cascade used to be delete-orphan)
    d = db.query(Draw).first()
    if d:
        db.delete(d)
        db.commit()
    after = _count_society_keys()
    db.close()
    assert after == before, "Society key was deleted when a draw was removed!"


def test_deleting_user_does_not_delete_society_key():
    """Expected behaviour: removing a regular user must NOT remove the shared
    society key (it has user_id=0, not the deleted user's id)."""
    db = SessionLocal()
    u = db.query(User).filter(User.username == "erin").first()
    has_society = _count_society_keys() > 0
    if u:
        db.delete(u)
        db.commit()
    gone = _count_society_keys() == 0
    db.close()
    assert has_society and not gone, "Society key should survive user deletion."


if __name__ == "__main__":
    test_society_key_survives_logout_login_cycle()
    print("PASS: society key survives logout/login cycle")
    test_anonymous_cannot_access_my_keys()
    print("PASS: anonymous cannot access my-keys (redirected to login)")
    test_society_key_prizes_after_draw()
    print("PASS: society key prizes computed after draw")
    test_deleting_a_draw_does_not_delete_society_key()
    print("PASS: deleting a draw does not delete society key")
    test_deleting_user_does_not_delete_society_key()
    print("PASS: deleting a user does not delete society key")
    print("\nALL TESTS PASSED")
