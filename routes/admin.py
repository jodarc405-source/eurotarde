import json
from datetime import date
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.auth_service import get_all_users, update_user_password, get_user_by_id, create_user, hash_password
from services.draw_service import create_draw, get_draw_by_date, get_all_draws, delete_draw
from services.euromillions_api import fetch_all_draws_last_n_months, fetch_latest_draw
from models.prize import PrizeTier
from models.user import User
from models.draw import Draw
from services.flash_service import flash

router = APIRouter()


@router.get("/admin/users", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    users = get_all_users(db)
    return request.app.state.templates.TemplateResponse("admin/users.html", {
        "request": request,
        "users": users,
    })


@router.get("/admin/users/create", response_class=HTMLResponse)
async def create_user_page(request: Request):
    return request.app.state.templates.TemplateResponse("admin/user_create.html", {
        "request": request,
    })


@router.post("/admin/users/create")
async def create_user_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: bool = Form(False),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.username == username).first()
    if not existing:
        create_user(db, username=username, email=email, password=password)
        if is_admin:
            user = db.query(User).filter(User.username == username).first()
            user.is_admin = True
            db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/admin/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if not user:
        return RedirectResponse(url="/admin/users", status_code=302)
    return request.app.state.templates.TemplateResponse("admin/user_edit.html", {
        "request": request,
        "user": user,
    })


@router.post("/admin/users/{user_id}/edit")
async def edit_user_submit(
    user_id: int,
    request: Request,
    username: str = Form(None),
    email: str = Form(None),
    new_password: str = Form(None),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user:
        if username and username != user.username:
            existing = db.query(User).filter(User.username == username, User.id != user_id).first()
            if not existing:
                user.username = username
        if email and email != user.email:
            existing = db.query(User).filter(User.email == email, User.id != user_id).first()
            if not existing:
                user.email = email
        if new_password:
            update_user_password(db, user_id, new_password)
        user.is_active = bool(is_active)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/admin/users/{user_id}/delete")
async def delete_user_route(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_user_by_id(db, user_id)
    if user and not user.is_admin:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/admin/prizes", response_class=HTMLResponse)
async def list_prizes(request: Request, db: Session = Depends(get_db)):
    tiers = db.query(PrizeTier).order_by(PrizeTier.tier).all()
    return request.app.state.templates.TemplateResponse("admin/prizes.html", {
        "request": request,
        "tiers": tiers,
    })


@router.post("/admin/prizes/update")
async def update_prizes(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    tiers = db.query(PrizeTier).order_by(PrizeTier.tier).all()
    for tier in tiers:
        key = f"prize_{tier.tier}"
        if key in form:
            try:
                tier.prize_amount = float(form[key])
            except ValueError:
                pass
    db.commit()
    return RedirectResponse(url="/admin/prizes", status_code=302)


@router.get("/admin/draws/manual", response_class=HTMLResponse)
async def manual_draw_page(request: Request):
    return request.app.state.templates.TemplateResponse("admin/draw_manual.html", {
        "request": request,
    })


@router.post("/admin/draws/manual")
async def manual_draw_submit(
    request: Request,
    draw_date: str = Form(...),
    n1: int = Form(...), n2: int = Form(...), n3: int = Form(...), n4: int = Form(...), n5: int = Form(...),
    s1: int = Form(...), s2: int = Form(...),
    prize_total: float = Form(0.0),
    db: Session = Depends(get_db),
):
    d = date.fromisoformat(draw_date)
    numbers = sorted([n1, n2, n3, n4, n5])
    stars = sorted([s1, s2])
    existing = get_draw_by_date(db, d)
    if not existing:
        create_draw(db, d, numbers, stars, prize_total, is_manual=True)
    return RedirectResponse(url="/sorteios", status_code=302)


@router.get("/admin/draws/import", response_class=HTMLResponse)
async def import_draws_page(request: Request, db: Session = Depends(get_db)):
    from models.draw import Draw
    existing_count = db.query(Draw).count()
    return request.app.state.templates.TemplateResponse("admin/draw_import.html", {
        "request": request,
        "existing_count": existing_count,
    })


@router.post("/admin/draws/import")
async def import_draws_submit(request: Request, db: Session = Depends(get_db)):
    from datetime import date as date_t
    draws = fetch_all_draws_last_n_months(months=6)
    added = 0
    for draw_data in draws:
        if not draw_data or not draw_data.get("numbers"):
            continue
        draw_date = date_t.fromisoformat(draw_data["date"])
        existing = get_draw_by_date(db, draw_date)
        if not existing:
            create_draw(
                db,
                draw_date=draw_date,
                numbers=draw_data["numbers"],
                stars=draw_data["stars"],
                prize_total=draw_data.get("prize_total", 0.0),
                is_manual=False,
            )
            added += 1
    return RedirectResponse(url="/sorteios?imported=" + str(added), status_code=302)


@router.post("/admin/draws/clear")
async def clear_draws_submit(request: Request, db: Session = Depends(get_db)):
    """Delete all draws from the database."""
    db.query(Draw).delete()
    db.commit()
    return RedirectResponse(url="/admin/draws/import", status_code=302)


@router.get("/admin/society-key", response_class=HTMLResponse)
async def society_key_page(request: Request, db: Session = Depends(get_db)):
    from services.my_keys_service import get_society_key
    society_key = get_society_key(db)
    return request.app.state.templates.TemplateResponse("admin/society_key.html", {
        "request": request,
        "society_key": society_key,
    })


@router.post("/admin/society-key/create")
async def society_key_submit(
    request: Request,
    n1: int = Form(...), n2: int = Form(...), n3: int = Form(...), n4: int = Form(...), n5: int = Form(...),
    s1: int = Form(...), s2: int = Form(...),
    label: str = Form("Chave da Sociedade"),
    db: Session = Depends(get_db),
):
    from services.my_keys_service import create_society_key
    numbers = sorted([n1, n2, n3, n4, n5])
    stars = sorted([s1, s2])
    create_society_key(db, numbers, stars, label)
    return RedirectResponse(url="/admin/society-key", status_code=302)


@router.post("/admin/keys/cleanup")
async def cleanup_test_keys(request: Request, db: Session = Depends(get_db)):
    """Delete test/seed keys: any key with user_id=0 that is NOT the society key."""
    from models.key import Key
    deleted = db.query(Key).filter(
        Key.user_id == 0,
        Key.is_society == False,
    ).delete()
    db.commit()
    flash(request, f"{deleted} chave(s) de teste apagada(s).", "success")
    return RedirectResponse(url="/admin/society-key", status_code=302)
