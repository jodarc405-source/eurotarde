import json
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.draw_service import get_draws, get_draw_by_id, get_distinct_years, get_distinct_months
from services.key_checker import check_key_against_draw, determine_prize
from services.my_keys_service import get_society_key_results, get_society_key, check_all_my_keys_against_draw, check_society_key_against_draw
from services.auth_service import require_auth
from models.prize import PrizeTier

router = APIRouter()


# ========== CHAVE DA SOCIEDADE (must be before /{draw_id}) ==========
# Users no longer create their own keys — everything is based on the single
# society key created by the admin. This page shows the society key results.

@router.get("/sorteios/my-keys", response_class=HTMLResponse,
            dependencies=[Depends(require_auth)])
async def my_keys_page(request: Request, db: Session = Depends(get_db)):
    from services.my_keys_service import get_society_key_results, get_society_key
    all_results = get_society_key_results(db)
    society_key = get_society_key(db)
    return request.app.state.templates.TemplateResponse("draws/my_keys.html", {
        "request": request,
        "all_results": all_results,
        "is_society": True,
        "society_key": society_key,  # None if not yet created
    })


@router.post("/sorteios/my-keys/create")
async def my_keys_create(
    request: Request,
    n1: int = Form(...), n2: int = Form(...), n3: int = Form(...), n4: int = Form(...), n5: int = Form(...),
    s1: int = Form(...), s2: int = Form(...),
    label: str = Form("Chave da Sociedade"),
    db: Session = Depends(get_db),
):
    """Create the society key (shared by all users).

    Any authenticated user may create it when it does not yet exist.
    The admin can also do this from /admin/society-key.
    """
    from services.my_keys_service import create_society_key
    numbers = sorted([n1, n2, n3, n4, n5])
    stars = sorted([s1, s2])
    create_society_key(db, numbers, stars, label)
    return RedirectResponse(url="/sorteios/my-keys", status_code=302)


# ========== LIST & DETAIL ==========

@router.get("/sorteios", response_class=HTMLResponse)
async def list_draws(
    request: Request,
    week: int = Query(None),
    month: int = Query(None),
    year: int = Query(None),
    imported: str = Query(None),
    db: Session = Depends(get_db),
):
    draws = get_draws(db, week=week, month=month, year=year)
    years = get_distinct_years(db)
    months = get_distinct_months(db, year=year) if year else []

    # For each draw, check if the society key won a prize
    draw_results = {}
    my_keys_list = []  # list of {numbers: [...], stars: [...]}
    society_key = get_society_key(db)
    if society_key:
        my_keys_list = [{
            "numbers": json.loads(society_key.numbers),
            "stars": json.loads(society_key.stars)
        }]
        for draw in draws:
            results = check_society_key_against_draw(db, draw.id)
            wins = [r for r in results if r["prize"] > 0]
            if wins:
                draw_results[draw.id] = wins

    return request.app.state.templates.TemplateResponse("draws/list.html", {
        "request": request,
        "draws": draws,
        "years": years,
        "months": months,
        "selected_week": week,
        "selected_month": month,
        "selected_year": year,
        "draw_results": draw_results,
        "my_keys_list": my_keys_list,
        "imported": imported,
    })


@router.get("/sorteios/{draw_id}", response_class=HTMLResponse)
async def draw_detail(draw_id: int, request: Request, db: Session = Depends(get_db)):
    draw = get_draw_by_id(db, draw_id)
    if not draw:
        return RedirectResponse(url="/sorteios", status_code=302)
    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)

    # Check society key for this draw
    my_keys_wins = []
    society_key = get_society_key(db)
    if society_key:
        my_keys_wins = check_society_key_against_draw(db, draw_id)
        my_keys_wins = [w for w in my_keys_wins if w["prize"] > 0]

    # Get society key for highlighting
    my_keys_list = []
    if society_key:
        my_keys_list = [{
            "numbers": json.loads(society_key.numbers),
            "stars": json.loads(society_key.stars)
        }]

    # Prize breakdown — use the REAL per-draw Portugal amounts when stored,
    # falling back to the static prize_tiers table otherwise.
    from services.prize_service import get_draw_prizes
    real_prizes = get_draw_prizes(db, draw.id)
    if real_prizes:
        prize_breakdown = [
            {"name": k, "prize": float(v)} for k, v in real_prizes.items()
        ]
    else:
        prize_tiers = db.query(PrizeTier).filter(PrizeTier.is_active == True).order_by(PrizeTier.tier).all()
        prize_breakdown = [{"name": t.name, "prize": float(t.prize_amount)} for t in prize_tiers]

    return request.app.state.templates.TemplateResponse("draws/detail.html", {
        "request": request,
        "draw": draw,
        "draw_numbers": draw_numbers,
        "draw_stars": draw_stars,
        "my_keys_wins": my_keys_wins,
        "my_keys_list": my_keys_list,
        "prize_breakdown": prize_breakdown,
    })
