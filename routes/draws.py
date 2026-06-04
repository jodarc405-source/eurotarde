import json
from fastapi import APIRouter, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.draw_service import get_draws, get_draw_by_id, get_distinct_years, get_distinct_months
from services.key_checker import check_key_against_draw, determine_prize, create_key_for_user, check_user_keys_for_draw
from models.prize import PrizeTier

router = APIRouter()


@router.get("/sorteios", response_class=HTMLResponse)
async def list_draws(
    request: Request,
    week: int = Query(None),
    month: int = Query(None),
    year: int = Query(None),
    db: Session = Depends(get_db),
):
    draws = get_draws(db, week=week, month=month, year=year)
    years = get_distinct_years(db)
    months = get_distinct_months(db, year=year) if year else []
    return request.app.state.templates.TemplateResponse("draws/list.html", {
        "request": request,
        "draws": draws,
        "years": years,
        "months": months,
        "selected_week": week,
        "selected_month": month,
        "selected_year": year,
    })


@router.get("/sorteios/{draw_id}", response_class=HTMLResponse)
async def draw_detail(draw_id: int, request: Request, db: Session = Depends(get_db)):
    draw = get_draw_by_id(db, draw_id)
    if not draw:
        return RedirectResponse(url="/sorteios", status_code=302)
    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)
    return request.app.state.templates.TemplateResponse("draws/detail.html", {
        "request": request,
        "draw": draw,
        "draw_numbers": draw_numbers,
        "draw_stars": draw_stars,
    })


@router.get("/sorteios/check", response_class=HTMLResponse)
async def check_keys_page(request: Request, db: Session = Depends(get_db)):
    draws = get_draws(db)
    return request.app.state.templates.TemplateResponse("draws/check_keys.html", {
        "request": request,
        "draws": draws,
        "result": None,
    })


@router.post("/sorteios/check")
async def check_keys_submit(
    request: Request,
    draw_id: int = Form(...),
    n1: int = Form(...),
    n2: int = Form(...),
    n3: int = Form(...),
    n4: int = Form(...),
    n5: int = Form(...),
    s1: int = Form(...),
    s2: int = Form(...),
    db: Session = Depends(get_db),
):
    user_id = request.session.get("user_id")
    draw = get_draw_by_id(db, draw_id)
    if not draw:
        return RedirectResponse(url="/sorteios", status_code=302)

    numbers = sorted([n1, n2, n3, n4, n5])
    stars = sorted([s1, s2])
    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)

    matched_numbers, matched_stars = check_key_against_draw(numbers, stars, draw_numbers, draw_stars)
    prize_tiers = db.query(PrizeTier).filter(PrizeTier.is_active == True).all()
    prize = determine_prize(matched_numbers, matched_stars, prize_tiers, draw.prize_total)

    # Save the key if user is logged in
    if user_id:
        create_key_for_user(db, user_id, draw_id, numbers, stars)

    draws = get_draws(db)
    return request.app.state.templates.TemplateResponse("draws/check_keys.html", {
        "request": request,
        "draws": draws,
        "result": {
            "draw": draw,
            "draw_numbers": draw_numbers,
            "draw_stars": draw_stars,
            "user_numbers": numbers,
            "user_stars": stars,
            "matched_numbers": matched_numbers,
            "matched_stars": matched_stars,
            "prize": prize,
        },
    })
