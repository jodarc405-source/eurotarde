"""Test: only the ADMIN may create the society key from /sorteios/my-keys.

Per the user's rule reversal (2026-07-21): the Chave da Sociedade is the single
shared key used for ALL users and for the Sorteios highlight. Only the admin may
create or change it. Non-admins must NOT see the create form, and a non-admin POST
to /sorteios/my-keys/create must be rejected (HTTP 403 -> redirect with warning).
"""
import os
import sys
import tempfile

sys.path.insert(0, ".")

db_path = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["***REDACTED***"] = "test-secret-key-for-smoke-test"
os.environ["ADMIN_DEFAULT_USERNAME"] = "admin"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "admin123"

from database import init_db, SessionLocal
init_db()

from services.auth_service import hash_password
from models.user import User
db = SessionLocal()
if not db.query(User).filter(User.username == "joao").first():
    db.add(User(
        username="joao", email="joao@test.pt",
        hashed_password=hash_password("pass123"),
        is_admin=False, is_active=True,
    ))
    db.commit()
db.close()

from fastapi.testclient import TestClient
import main
client = TestClient(main.app)

# --- Non-admin flow ---
r = client.post("/auth/login", data={"username": "joao", "password": "pass123"})
assert r.status_code in (200, 302), f"login failed: {r.status_code}"
print("PASS: non-admin login")

# Access my-keys page — should NOT show create form (admin-only)
r = client.get("/sorteios/my-keys")
assert r.status_code == 200, f"my-keys failed: {r.status_code}"
assert "action=\"/sorteios/my-keys/create\"" not in r.text, "create form shown to non-admin"
assert "apenas o" in r.text.lower() or "administrador" in r.text.lower(), "no admin-only notice"
print("PASS: non-admin does NOT see create form (admin-only notice shown)")

# Non-admin POST must be rejected (403 -> redirect to my-keys with warning)
r = client.post("/sorteios/my-keys/create", data={
    "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
    "s1": 1, "s2": 2, "label": "Chave da Sociedade"
}, follow_redirects=False)
assert r.status_code in (302, 403), f"expected 302/403, got {r.status_code}"
print("PASS: non-admin create blocked (403)")

# Verify NO society key exists after the blocked attempt
db = SessionLocal()
from models.key import Key
sk = db.query(Key).filter(Key.is_society == True).first()
db.close()
assert sk is None, "society key should NOT exist after non-admin attempt"
print("PASS: no society key created by non-admin")

# --- Admin flow (separate client / fresh login) ---
client.post("/auth/logout", follow_redirects=True)
r = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
assert r.status_code in (200, 302), f"admin login failed: {r.status_code}"
print("PASS: admin login")

# Admin sees the create form when no society key exists
r = client.get("/sorteios/my-keys")
assert "action=\"/sorteios/my-keys/create\"" in r.text, "admin should see create form"
print("PASS: admin sees create form when no society key")

# Admin creates the society key
r = client.post("/sorteios/my-keys/create", data={
    "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
    "s1": 1, "s2": 2, "label": "Chave da Sociedade"
}, follow_redirects=False)
assert r.status_code == 302, f"admin create failed: {r.status_code}"
print("PASS: admin can create society key")

db = SessionLocal()
sk = db.query(Key).filter(Key.is_society == True).first()
db.close()
assert sk is not None, "society key not created by admin"
print("PASS: society key in DB (id=%s)" % sk.id)

print("\nALL SOCIETY-KEY ACCESS-CONTROL TESTS PASSED")
