"""Smoke test for Eurotarde society-key + spend-prizes features."""
import os
import sys
import tempfile

sys.path.insert(0, ".")

# Use an isolated SQLite DB
db_path = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
os.environ["***REDACTED***"] = "test-secret-key-for-smoke-test"
os.environ["ADMIN_DEFAULT_USERNAME"] = "admin"
os.environ["ADMIN_DEFAULT_PASSWORD"] = "admin123"

from fastapi.testclient import TestClient
import main
from database import init_db, SessionLocal
from models.user import User
from services.auth_service import hash_password, create_user
from services.my_keys_service import create_society_key, get_society_prizes_2026
from services.payment_service import spend_prizes_on_users, get_total_society_payouts

# Init DB (creates tables, admin user, prize tiers)
main.init_db()

client = TestClient(main.app)

# 1. Login as admin
r = client.post("/auth/login", data={"username": "admin", "password": "admin123"})
assert r.status_code in (302, 200), f"login failed: {r.status_code}"
print("PASS: admin login")

# 2. Create society key
r = client.post("/admin/society-key/create", data={
    "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5,
    "s1": 1, "s2": 2, "label": "Chave da Sociedade"
}, follow_redirects=False)
assert r.status_code == 302, f"society key create failed: {r.status_code}"
print("PASS: society key created")

# Verify it exists
db = SessionLocal()
from models.key import Key
society = db.query(Key).filter(Key.is_society == True).first()
assert society is not None, "society key not found in DB"
print(f"PASS: society key in DB (id={society.id})")

# 3. Create 5 regular users
for i in range(1, 6):
    create_user(db, username=f"user{i}", email=f"user{i}@test.pt", password="pass123")
db.close()
print("PASS: 5 users created")

# 4. Check home page shows prizes 2026 (0 if no draws)
r = client.get("/")
assert r.status_code == 200, f"home failed: {r.status_code}"
assert "Prémios 2026" in r.text, "home missing prizes 2026"
print("PASS: home page renders with Prémios 2026")

# 5. Check my-keys page (society key)
r = client.get("/sorteios/my-keys")
assert r.status_code == 200, f"my-keys failed: {r.status_code}"
assert b"Chave da Sociedade" in r.content, "society key not shown"
print("PASS: society key page renders")

# 6. Test spend-prizes with empty pool (should not crash)
# Note: we DON'T call spend_prizes_on_users here to avoid creating an empty pool
# that would shadow the real one. Just verify the route handles empty pool.
r = client.post("/pagamentos/spend-prizes", follow_redirects=False)
assert r.status_code == 302, f"spend-prizes POST (empty) failed: {r.status_code}"
print("PASS: spend-prizes with empty pool = no crash")

# 7. Test spend-prizes with a pool of 6€ (5 users -> 5€ distributed, 1€ remaining)
db = SessionLocal()
from services.payment_service import top_up_prize_pool
top_up_prize_pool(db, 6.0)
db.close()

r = client.post("/pagamentos/spend-prizes", follow_redirects=False)
assert r.status_code == 302, f"spend-prizes POST failed: {r.status_code}"
print("PASS: spend-prizes POST ok")

db = SessionLocal()
# Re-check: pool should have 1€ left, 5 payments of 1€ created
from models.payment import Payment
from models.prize_pool import PrizePool
payments = db.query(Payment).filter(Payment.notes.like("Prémio distribuído%")).all()
total_payout = sum(p.amount for p in payments)
pool = db.query(PrizePool).order_by(PrizePool.id).first()
db.close()

assert len(payments) == 5, f"expected 5 payments, got {len(payments)}"
assert abs(total_payout - 5.0) < 0.01, f"expected 5€ total payout, got {total_payout}"
assert abs(pool.available - 1.0) < 0.01, f"expected 1€ remaining, got {pool.available}"
print(f"PASS: 6€ pool -> 5€ distributed (1€/user x5), 1€ remaining")

# 8. Verify 'prémio utilizado' sum
db = SessionLocal()
used = get_total_society_payouts(db)
db.close()
assert abs(used - 5.0) < 0.01, f"expected prémio utilizado = 5€, got {used}"
print(f"PASS: prémio utilizado = {used}€")

# 9. Payments page shows the €1 entries highlighted
r = client.get("/pagamentos")
assert r.status_code == 200, f"pagamentos failed: {r.status_code}"
assert b"table-warning" in r.content, "spend-prizes payments not highlighted"
print("PASS: payments page highlights €1 entries")

# 10. Test draws list shows society key as "premiada" when it wins
# Create a draw matching the society key numbers (1,2,3,4,5 + 1,2 stars)
from services.draw_service import create_draw
from datetime import date
db = SessionLocal()
# Society key is 1,2,3,4,5 + 1,2 (set in step 2). Make a draw with same numbers.
create_draw(db, date(2026, 1, 2), [1, 2, 3, 4, 5], [1, 2], prize_total=100.0, is_manual=True)
db.close()

r = client.get("/sorteios")
assert r.status_code == 200, f"sorteios list failed: {r.status_code}"
# The draw should show the society key as "Chave premiada" (singular, 1 key)
assert "Chave premiada" in r.text, "sorteios list missing 'Chave premiada' for society key"
print("PASS: sorteios list shows society key as 'Chave premiada'")

print("\nALL SMOKE TESTS PASSED")
