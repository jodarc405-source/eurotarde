import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from services.payment_service import get_total_payments_by_user, get_monthly_payment_totals, get_all_users_weeks
from services.auth_service import get_all_users
from services.draw_service import get_all_draws
from models.key import Key

router = APIRouter()


@router.get("/api/charts/prizes-per-user")
async def prizes_per_user(db: Session = Depends(get_db)):
    users = get_all_users(db)
    data = []
    for user in users:
        keys = db.query(Key).filter(Key.user_id == user.id, Key.prize_won > 0).all()
        total = sum(k.prize_won for k in keys)
        data.append({"username": user.username, "total_prizes": total, "count": len(keys)})
    return JSONResponse(content=data)


@router.get("/api/charts/payment-history")
async def payment_history(db: Session = Depends(get_db)):
    monthly = get_monthly_payment_totals(db)
    return JSONResponse(content=monthly)


@router.get("/api/charts/user-stats")
async def user_stats(db: Session = Depends(get_db)):
    users = get_all_users(db)
    draws = get_all_draws(db)
    total_prizes = db.query(func.sum(Key.prize_won)).scalar() or 0
    return JSONResponse(content={
        "total_users": len(users),
        "total_draws": len(draws),
        "total_prizes_paid": float(total_prizes),
    })


@router.get("/api/draws")
async def api_draws(
    week: int = None, month: int = None, year: int = None,
    db: Session = Depends(get_db),
):
    from services.draw_service import get_draws
    draws = get_draws(db, week=week, month=month, year=year)
    result = []
    for d in draws:
        result.append({
            "id": d.id,
            "date": d.draw_date.isoformat(),
            "numbers": json.loads(d.numbers),
            "stars": json.loads(d.stars),
            "prize_total": d.prize_total,
        })
    return JSONResponse(content=result)


@router.get("/api/charts/weeks-per-user")
async def weeks_per_user(db: Session = Depends(get_db)):
    data = get_all_users_weeks(db)
    return JSONResponse(content=data)


@router.post("/api/keys/check")
async def api_check_key(
    request: Request,
    db: Session = Depends(get_db),
):
    body = await request.json()
    draw_id = body.get("draw_id")
    numbers = body.get("numbers", [])
    stars = body.get("stars", [])

    from services.draw_service import get_draw_by_id
    from services.key_checker import check_key_against_draw, determine_prize
    from models.prize import PrizeTier

    draw = get_draw_by_id(db, draw_id)
    if not draw:
        return JSONResponse(content={"error": "Draw not found"}, status_code=404)

    draw_numbers = json.loads(draw.numbers)
    draw_stars = json.loads(draw.stars)
    mn, ms = check_key_against_draw(numbers, stars, draw_numbers, draw_stars)
    tiers = db.query(PrizeTier).filter(PrizeTier.is_active == True).all()
    prize = determine_prize(mn, ms, tiers, draw.prize_total)

    return JSONResponse(content={
        "matched_numbers": mn,
        "matched_stars": ms,
        "prize": prize,
        "draw_numbers": draw_numbers,
        "draw_stars": draw_stars,
    })
