"""Smoke test: society key (no double-count) + cleanup test keys."""
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

from fastapi.testclient import TestClient
import main
client = TestClient(main.app)
client.post("/auth/login", data={"username": "admin", "password": "admin123"})

# Create society key (1,2,3,4,5 + 1,2)
client.post("/admin/society-key/create", data={
    "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
    "s1": 1, "s2": 2, "label": "Chave da Sociedade"
}, follow_redirects=False)
print("PASS: society key created")

# Create 2 TEST keys with user_id=0 (simulating seed/test keys)
db = SessionLocal()
from models.key import Key
import json
for i in range(2):
    k = Key(user_id=0, draw_id=0,
             numbers=json.dumps(sorted([10,20,30,40,50])),
             stars=json.dumps(sorted([5,6])),
             is_society=False)
    db.add(k)
db.commit()
db.close()
print("PASS: 2 test keys created (user_id=0, is_society=False)")

# Create a draw matching the society key (1,2,3,4,5 + 1,2)
from services.draw_service import create_draw
from datetime import date
db = SessionLocal()
create_draw(db, date(2026, 1, 2), [1, 2, 3, 4, 5], [1, 2], prize_total=100.0, is_manual=True)
db.close()
print("PASS: draw created matching society key")

# Check the draws list — should show ONLY society key win, not test keys
r = client.get("/sorteios")
assert r.status_code == 200, f"sorteios failed: {r.status_code}"
# The draw should show the society key as "Chave premiada" (singular, 1 key),
# NOT "3 chaves" (no double-count from the test keys).
assert "Chave premiada" in r.text, "Expected society key win shown as 'Chave premiada'"
assert "3 chaves" not in r.text, "Double-count detected: 3 keys shown instead of 1"
print("PASS: draws list shows only society key win (no double-count)")

# Test cleanup route
r = client.post("/admin/keys/cleanup", follow_redirects=False)
assert r.status_code == 302, f"cleanup failed: {r.status_code}"
db = SessionLocal()
remaining = db.query(Key).filter(Key.user_id == 0, Key.is_society == False).count()
society = db.query(Key).filter(Key.is_society == True).count()
db.close()
assert remaining == 0, f"Expected 0 test keys, got {remaining}"
assert society == 1, f"Expected 1 society key, got {society}"
print("PASS: cleanup removed test keys, kept society key")

# Home should show prize for the 1 win (not doubled)
r = client.get("/")
assert "100,00" in r.text or "100.00" in r.text, "Home should show 100€ prize"
print("PASS: home shows correct prize (no double-count)")

print("\nALL SOCIETY-KEY SMOKE TESTS PASSED")
