from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from services.draw_service import get_all_draws
from services.my_keys_service import get_all_my_keys_results, check_all_my_keys_against_draw
from services.analytics import (
    get_total_views, get_today_views, get_views_this_week,
    get_unique_visitors_today, get_unique_visitors_total, get_top_pages,
    get_views_last_7_days,
)
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

    # Prémios 2026 = soma dos prémios da CHAVE DA SOCIEDADE (criada pelo admin)
    # em todos os sorteios de 2026.
    from services.my_keys_service import get_society_prizes_2026
    total_prizes_2026 = get_society_prizes_2026(db)

    # Prémio utilizado = soma dos pagamentos de 1€ (gastar prémios) dividido
    # pelos utilizadores (cada utilizador recebe 1€ por ação de "gastar prémios").
    from services.payment_service import get_total_society_payouts
    premio_utilizado = get_total_society_payouts(db)

    # Analytics — only for admin
    analytics = None
    user_id = request.session.get('user_id', 0)
    current_user = db.query(User).filter(User.id == user_id).first()
    if current_user and current_user.is_admin:
        analytics = {
            "total_views": get_total_views(db),
            "today_views": get_today_views(db),
            "week_views": get_views_this_week(db),
            "unique_visitors_today": get_unique_visitors_today(db),
            "unique_visitors_total": get_unique_visitors_total(db),
            "top_pages": get_top_pages(db, limit=10),
            "views_last_7_days": get_views_last_7_days(db),
        }

    return request.app.state.templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "users": users,
        "draws": draws,
        "total_prizes_2026": float(total_prizes_2026),
        "premio_utilizado": float(premio_utilizado),
        "analytics": analytics,
    })
