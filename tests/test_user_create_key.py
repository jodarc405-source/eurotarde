"""Smoke test: non-admin user can create the society key from /sorteios/my-keys."""
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

# Login as normal user (Starlette TestClient follows redirects → 200 on success)
r = client.post("/auth/login", data={"username": "joao", "password": "pass123"})
assert r.status_code in (200, 302), f"login failed: {r.status_code}"
print("PASS: non-admin login")

# Access my-keys page — should show create form (no society key yet)
r = client.get("/sorteios/my-keys")
assert r.status_code == 200, f"my-keys failed: {r.status_code}"
assert "Criar Chave da Sociedade" in r.text, "create form not shown"
print("PASS: non-admin sees create form when no society key")

# Create the society key as non-admin
r = client.post("/sorteios/my-keys/create", data={
    "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
    "s1": 1, "s2": 2, "label": "Chave da Sociedade"
}, follow_redirects=False)
assert r.status_code == 302, f"create failed: {r.status_code}"
print("PASS: non-admin can create society key")

# Verify it exists in DB
db = SessionLocal()
from models.key import Key
sk = db.query(Key).filter(Key.is_society == True).first()
db.close()
assert sk is not None, "society key not created"
print("PASS: society key in DB (id=%s)" % sk.id)

# Page now shows results, not create form
r = client.get("/sorteios/my-keys")
assert "Criar Chave da Sociedade" not in r.text, "form still shown after creation"
print("PASS: create form hidden after key exists")

print("\nALL NON-ADMIN CREATE TESTS PASSED")
