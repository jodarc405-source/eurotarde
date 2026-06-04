from datetime import date
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.payment_service import (
    create_payment, get_payments, get_payment_by_id,
    update_payment, delete_payment, get_all_payments
)
from services.auth_service import get_all_users
from services.draw_service import get_all_draws

router = APIRouter()


@router.get("/pagamentos", response_class=HTMLResponse)
async def list_payments(request: Request, db: Session = Depends(get_db)):
    payments = get_all_payments(db)
    return request.app.state.templates.TemplateResponse("payments/list.html", {
        "request": request,
        "payments": payments,
    })


@router.get("/pagamentos/create", response_class=HTMLResponse)
async def create_payment_page(request: Request, db: Session = Depends(get_db)):
    users = get_all_users(db)
    draws = get_all_draws(db)
    return request.app.state.templates.TemplateResponse("payments/create.html", {
        "request": request,
        "users": users,
        "draws": draws,
    })


@router.post("/pagamentos/create")
async def create_payment_submit(
    request: Request,
    user_id: int = Form(...),
    draw_id: int = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    create_payment(db, user_id, draw_id, amount, date.fromisoformat(payment_date), notes)
    return RedirectResponse(url="/pagamentos", status_code=302)


@router.get("/pagamentos/{payment_id}/edit", response_class=HTMLResponse)
async def edit_payment_page(payment_id: int, request: Request, db: Session = Depends(get_db)):
    payment = get_payment_by_id(db, payment_id)
    if not payment:
        return RedirectResponse(url="/pagamentos", status_code=302)
    users = get_all_users(db)
    draws = get_all_draws(db)
    return request.app.state.templates.TemplateResponse("payments/edit.html", {
        "request": request,
        "payment": payment,
        "users": users,
        "draws": draws,
    })


@router.post("/pagamentos/{payment_id}/edit")
async def edit_payment_submit(
    payment_id: int,
    request: Request,
    user_id: int = Form(...),
    draw_id: int = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    update_payment(db, payment_id, amount, date.fromisoformat(payment_date), notes)
    return RedirectResponse(url="/pagamentos", status_code=302)


@router.post("/pagamentos/{payment_id}/delete")
async def delete_payment_route(payment_id: int, request: Request, db: Session = Depends(get_db)):
    delete_payment(db, payment_id)
    return RedirectResponse(url="/pagamentos", status_code=302)
