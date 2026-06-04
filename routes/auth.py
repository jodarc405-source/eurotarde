from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.auth_service import authenticate_user, create_user, get_user_by_username
from models.user import User

router = APIRouter()


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/auth/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user:
        return request.app.state.templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Utilizador ou palavra-passe inválidos."},
        )
    request.session["user_id"] = user.id
    request.session["is_admin"] = user.is_admin
    request.session["username"] = user.username
    return RedirectResponse(url="/", status_code=302)


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/auth/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    if password != confirm_password:
        return request.app.state.templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "As palavras-passes não coincidem."},
        )
    existing = get_user_by_username(db, username)
    if existing:
        return request.app.state.templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Este nome de utilizador já existe."},
        )
    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        return request.app.state.templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Este email já está registado."},
        )
    create_user(db, username, email, password)
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)
