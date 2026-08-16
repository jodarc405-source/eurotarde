import os, sys
from datetime import date
os.environ["DATABASE_URL"] = open(r"C:\Users\leozi\Projetos\neon_db_url.txt").read().strip()
sys.path.insert(0, r"C:\Users\leozi\Projetos\eurotarde")
from database import SessionLocal
from services.payment_service import get_user_weeks_paid

CURRENT = int(date.today().strftime("%V"))
print("Semana atual:", CURRENT)
db = SessionLocal()
for uid in [3, 4, 5, 6]:
    weeks = get_user_weeks_paid(db, uid, 2026)
    greens = [w["week_number"] for w in weeks if w["source"] == "payment"]
    oranges = [w["week_number"] for w in weeks if w["source"] == "prize"]
    auto_paid = [w["week_number"] for w in weeks if w["paid"] and w["source"] == "payment" and w["week_number"] > 24]  # auto green beyond explicit
    print(f"user {uid}: verde={greens[:3]}..{greens[-3:] if greens else []} ({len(greens)}) | laranja={oranges} ({len(oranges)})")
db.close()
