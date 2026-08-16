r"""Seed manual da tabela week_payments com o mapeamento exato pedido pelo user.

Corre da maquina local contra a Neon. Idempotente: limpa as rows do ano atual
e re-insere. IMPORTANTE: a logica de semanas NAO auto-marca semanas ate a
atual como pagas — so o que esta aqui gravado aparece pago.

Regras finais (2026-08-16):
  Adérito(3): verde 1-14, laranja 15-23   (24-52 cinzento)
  Helder(4):  verde 1-19, laranja 20-28   (29-52 cinzento)
  Hugo(5):    verde 1-12, laranja 13-21    (22-52 cinzento)
  João(6):    verde 1-15, laranja 16-24    (25-52 cinzento)
  Miguel(2):  verde 1-14, laranja 15-24, verde 25-52
"""
import os, sys
from datetime import date
os.environ["DATABASE_URL"] = open(
    r"C:\Users\leozi\Projetos\neon_db_url.txt", encoding="utf-8"
).read().strip()
sys.path.insert(0, r"C:\Users\leozi\Projetos\eurotarde")

from database import SessionLocal, init_db
from models.week_payment import WeekPayment

YEAR = 2026
# (user_id, [(start, end, source), ...])
PLAN = [
    (2, [(1, 14, "payment"), (15, 24, "prize"), (25, 52, "payment")]),
    (3, [(1, 14, "payment"), (15, 23, "prize")]),
    (4, [(1, 19, "payment"), (20, 28, "prize")]),
    (5, [(1, 12, "payment"), (13, 21, "prize")]),
    (6, [(1, 15, "payment"), (16, 24, "prize")]),
]

db = SessionLocal()
init_db()
# Limpa rows do ano para re-seed idempotente
db.query(WeekPayment).filter(WeekPayment.year == YEAR).delete()
db.commit()

written = 0
for uid, ranges in PLAN:
    for start, end, src in ranges:
        for w in range(start, end + 1):
            db.add(WeekPayment(user_id=uid, week_number=w, year=YEAR, source=src))
            written += 1
db.commit()

# Verifica
print("Inseridas:", written, "rows")
for uid, _ in PLAN:
    rows = db.query(WeekPayment).filter(
        WeekPayment.user_id == uid, WeekPayment.year == YEAR
    ).all()
    by = {}
    for r in rows:
        by[r.source] = by.get(r.source, 0) + 1
    print(f"  user {uid}: {by}")
db.close()
