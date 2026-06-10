from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from services.draw_service import get_all_draws
from services.my_keys_service import get_all_my_keys_results, check_all_my_keys_against_draw
from models.user import User
from models.draw import Draw
from datetime import date

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    # If not logged in, show landing page
    if not request.session.get('user_id'):
        return request.app.state.templates.TemplateResponse("landing.html", {
            "request": request,
        })

    users = db.query(User).filter(User.is_active == True).all()
    draws = get_all_draws(db)

    # My keys prize stats
    user_id = request.session.get('user_id', 0)
    my_keys_results = get_all_my_keys_results(db, user_id=user_id)
    my_keys_count = len(my_keys_results)
    my_keys_total_wins = sum(1 for d in my_keys_results.values() if d["wins"])
    my_keys_total_prize = sum(d["total_prize"] for d in my_keys_results.values())

    # Total prémios 2026 — cálculo dinâmico: verifica cada "minha chave" contra todos os draws de 2026
    year_start = date(2026, 1, 1)
    year_end = date(2026, 12, 31)
    draws_2026 = [d for d in draws if year_start <= d.draw_date <= year_end]
    total_prizes_2026 = 0.0
    for d in draws_2026:
        results = check_all_my_keys_against_draw(db, d.id, user_id=user_id)
        total_prizes_2026 += sum(r["prize"] for r in results)

    return request.app.state.templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "users": users,
        "draws": draws,
        "my_keys_count": my_keys_count,
        "my_keys_total_wins": my_keys_total_wins,
        "my_keys_total_prize": my_keys_total_prize,
        "total_prizes_2026": float(total_prizes_2026),
        "all_results": my_keys_results,
    })
