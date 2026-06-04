import json
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.draw_service import get_draws, get_draw_by_id, get_distinct_years, get_distinct_months
from services.key_checker import check_key_against_draw, determine_prize
from services.my_keys_service import (
    create_my_key, get_my_keys, get_my_key_by_id, delete_my_key,
    get_all_my_keys_results, check_all_my_keys_against_draw
)
from models.prize import PrizeTier

router = APIRouter()


# ========== MINHAS CHAVES (must be before /{draw_id}) ==========

@router.get("/sorteios/my-keys", response_class=HTMLResponse)
async def my_keys_page(request: Request, db: Session = Depends(get_db)):
    all_results = get_all_my_keys_results(db)
    return request.app.state.templates.TemplateResponse("draws/my_keys.html", {
        "request": request,
        "all_results": all_results,
    })


@router.post("/sorteios/my-keys/create")
async def my_keys_create(
    request: Request,
    n1: int = Form(...), n2: int = Form(...), n3: int = Form(...), n4: int = Form(...), n5: int = Form(...),
    s1: int = Form(...), s2: int = Form(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
):
    numbers = sorted([n1, n2, n3, n4, n5])
    stars = sorted([s1, s2])
    create_my_key(db, numbers, stars, label)
    return RedirectResponse(url="/sorteios/my-keys", status_code=302)


@router.post("/sorteios/my-keys/{key_id}/delete")
async def my_keys_delete(key_id: int, request: Request, db: Session = Depends(get_db)):
    delete_my_key(db, key_id)
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

    # For each draw, check if any of "my keys" won a prize
    draw_results = {}
    if request.session.get('is_admin'):
        for draw in draws:
            results = check_all_my_keys_against_draw(db, draw.id)
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
        "imported": imported,
    })


@router.get("/sorteios/{draw_id}", response_class=HTMLResponse)
async def draw_detail(draw_id: int, request: Request, db: Session = Depends(get_db)):
    draw = get_draw_by_id(db, draw_id)
    if not draw:
        return RedirectResponse(url="/sorteios", status_code=302)
    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)

    # Check my keys for this draw
    my_keys_wins = []
    if request.session.get('is_admin'):
        my_keys_wins = check_all_my_keys_against_draw(db, draw_id)
        my_keys_wins = [w for w in my_keys_wins if w["prize"] > 0]

    return request.app.state.templates.TemplateResponse("draws/detail.html", {
        "request": request,
        "draw": draw,
        "draw_numbers": draw_numbers,
        "draw_stars": draw_stars,
        "my_keys_wins": my_keys_wins,
    })
