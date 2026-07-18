"""Automated tests for Eurotarde key persistence & prize updates.

Run:  uv run python -m pytest tests/test_persistence.py -q
(or): uv run python tests/test_persistence.py
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
    check_all_my_keys_against_draw,
    get_my_keys,
    update_prizes_for_all_users,
)
from datetime import date  # noqa: E402

Base.metadata.create_all(bind=engine)
client = TestClient(main.app)


def _count_keys(uid):
    db = SessionLocal()
    n = db.query(Key).filter(Key.user_id == uid).count()
    db.close()
    return n


def test_key_survives_logout_login_cycle():
    """Regression test: a user's saved key must persist across logout+login."""
    client.post("/auth/register", data={
        "username": "dave", "email": "dave@x.com",
        "password": "secret123", "confirm_password": "secret123",
    })
    client.post("/auth/login", data={"username": "dave", "password": "secret123"})
    client.post("/sorteios/my-keys/create", data={
        "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
        "s1": 1, "s2": 2, "label": "Chave do Dave",
    })
    # fresh client == new session == re-login after logout/restart
    c2 = TestClient(main.app)
    c2.post("/auth/login", data={"username": "dave", "password": "secret123"})
    r = c2.get("/sorteios/my-keys")
    assert "Chave do Dave" in r.text, "Key disappeared after re-login!"
    # and it must be in the DB, not just shown
    db = SessionLocal()
    uid = db.query(User).filter(User.username == "dave").first().id
    db.close()
    assert _count_keys(uid) == 1, "Key row missing from DB after re-login!"


def test_prizes_update_per_user_after_draw():
    """Each user's my-keys prizes must be recomputed when a new draw arrives."""
    # setup user + a winning my-key (matches draw below)
    client.post("/auth/register", data={
        "username": "erin", "email": "erin@x.com",
        "password": "secret123", "confirm_password": "secret123",
    })
    client.post("/auth/login", data={"username": "erin", "password": "secret123"})
    client.post("/sorteios/my-keys/create", data={
        "n1": 10, "n2": 20, "n3": 30, "n4": 40, "n5": 50,
        "s1": 11, "s2": 12, "label": "Chave da Erin",
    })
    db = SessionLocal()
    uid = db.query(User).filter(User.username == "erin").first().id
    # create a draw that matches exactly (5+2 jackpot)
    draw = create_draw(db, date(2031, 5, 5),
                       [10, 20, 30, 40, 50], [11, 12],
                       prize_total=100000000.0, is_manual=True)
    # simulate scheduler behaviour for THIS user
    wins = check_all_my_keys_against_draw(db, draw.id, user_id=uid)
    db.close()

    assert len(wins) >= 1, "No win recorded for user's key!"
    assert wins[0]["prize"] > 0, "Prize not computed for user's key!"

    # update_prizes_for_all_users must include this user
    db = SessionLocal()
    summary = update_prizes_for_all_users(db)
    db.close()
    assert uid in summary, "User missing from prize recalculation summary!"
    assert summary[uid] > 0, "User total prize not updated!"


def test_anonymous_cannot_access_my_keys():
    """Unauthenticated requests to my-keys must be redirected to login,
    preventing silent save/read under user_id=0."""
    c = TestClient(main.app)
    r = c.get("/sorteios/my-keys")
    assert r.status_code in (302, 307), "Anonymous access to my-keys not blocked!"
    assert "/auth/login" in r.headers.get("location", ""), "Not redirected to login!"


def test_deleting_a_draw_does_not_delete_my_keys():
    """Admin 'clear draws' must NOT orphan-delete users' my-keys (draw_id=0)."""
    db = SessionLocal()
    u = db.query(User).filter(User.username == "erin").first()
    uid = u.id
    before = _count_keys_in_session(db, uid)
    # delete a draw (the cascade used to be delete-orphan)
    d = db.query(Draw).first()
    db.delete(d)
    db.commit()
    after = _count_keys_in_session(db, uid)
    db.close()
    assert after == before, "My-keys were deleted when a draw was removed!"


def _count_keys_in_session(db, uid):
    return db.query(Key).filter(Key.user_id == uid).count()


def test_deleting_user_deletes_their_keys():
    """Expected behaviour: removing a user removes their keys (cascade all)."""
    db = SessionLocal()
    u = db.query(User).filter(User.username == "erin").first()
    uid = u.id
    has_keys = _count_keys_in_session(db, uid) > 0
    db.delete(u)
    db.commit()
    gone = _count_keys_in_session(db, uid) == 0
    db.close()
    assert has_keys and gone, "User's keys not cleaned up on user deletion."


if __name__ == "__main__":
    test_key_survives_logout_login_cycle()
    print("PASS: key survives logout/login cycle")
    test_anonymous_cannot_access_my_keys()
    print("PASS: anonymous cannot access my-keys (redirected to login)")
    test_prizes_update_per_user_after_draw()
    print("PASS: prizes update per-user after draw")
    test_deleting_a_draw_does_not_delete_my_keys()
    print("PASS: deleting a draw does not delete my-keys")
    test_deleting_user_deletes_their_keys()
    print("PASS: deleting a user deletes their keys")
    print("\nALL TESTS PASSED")
