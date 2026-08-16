r"""Backfill de sorteios para a Neon, corrido da MAQUINA LOCAL (IP nao bloqueado).

O Render bloqueia o IP do web service (403 de euro-millions.com), por isso o
scheduler no Render nao importa novos sorteios. Este script corre localmente,
faz o scrape (que funciona do IP residencial), e escreve diretamente na Neon.

Usa a connection string da Neon (neon_db_url.txt). Nao precisa de alterar o repo.

Corre:
  C:\Users\leozi\Projetos\eurotarde\.venv\Scripts\python.exe backfill_neon.py
"""
import os, sys

# 1) Apontar para a Neon ANTES de importar nada que leia DATABASE_URL
os.environ["DATABASE_URL"] = open(
    r"C:\Users\leozi\Projetos\neon_db_url.txt", encoding="utf-8"
).read().strip()

REPO = r"C:\Users\leozi\Projetos\eurotarde"
sys.path.insert(0, REPO)

from database import SessionLocal
from services.euromillions_api import fetch_latest_draw, fetch_all_draws_last_n_months
from services.draw_service import get_draw_by_date, create_draw
from services.my_keys_service import check_society_key_against_draw
from models.draw import Draw

db = SessionLocal()
before = db.query(Draw).count()
print("Draws na Neon antes:", before)

# Importa os ultimos 6 meses (apanha 18-07 ate hoje)
draws = fetch_all_draws_last_n_months(months=6)
print("Draws encontrados no scrape:", len(draws))

added = 0
for d in draws:
    if not d or not d.get("numbers"):
        continue
    from datetime import date
    dd = date.fromisoformat(d["date"])
    if get_draw_by_date(db, dd):
        continue
    from services.euromillions_api import fetch_draw_prizes
    prizes = fetch_draw_prizes(d["date"])
    nd = create_draw(
        db, draw_date=dd, numbers=d["numbers"], stars=d["stars"],
        prize_total=d.get("prize_total", 0.0), is_manual=False, prizes=prizes,
    )
    added += 1
    check_society_key_against_draw(db, nd.id)

after = db.query(Draw).count()
db.close()
print("Adicionados:", added, "| Draws na Neon depois:", after)
