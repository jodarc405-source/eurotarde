from datetime import date
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.payment_service import (
    create_payment, get_payments, get_payment_by_id,
    update_payment, delete_payment, get_all_payments,
    spend_prizes_on_users, get_caixa
)
from services.auth_service import get_all_users
from services.draw_service import get_all_draws
from services.flash_service import flash

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
    draw_id: int = Form(None),
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db),
):
    did = int(draw_id) if draw_id and draw_id != "0" else None
    create_payment(db, user_id, did, amount, date.fromisoformat(payment_date), notes)
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


@router.get("/pagamentos/spend-prizes", response_class=HTMLResponse)
async def spend_prizes_page(request: Request, db: Session = Depends(get_db)):
    """Show the 'Gastar Prémios' page with user selection and amounts."""
    from models.user import User
    from services.payment_service import get_caixa
    from config import get_settings
    
    users = db.query(User).filter(User.is_admin == False, User.is_active == True).all()
    caixa = get_caixa(db)
    settings = get_settings()
    week_value = getattr(settings, 'WEEK_VALUE', 1.0)
    
    return request.app.state.templates.TemplateResponse("payments/spend_prizes.html", {
        "request": request,
        "users": users,
        "caixa": caixa,
        "total_prizes_2026": 0.0,  # Could fetch if needed
        "week_value": week_value,
    })


@router.post("/pagamentos/spend-prizes")
async def spend_prizes_route(request: Request, db: Session = Depends(get_db)):
    """Distribute available caixa as payments to selected users (gastar prémios)."""
    from services.payment_service import spend_prizes_on_users
    import json
    
    # Get form data
    form_data = await request.form()
    
    # Extract amounts per user
    user_amounts = {}
    for key, value in form_data.items():
        if key.startswith('amount_'):
            user_id = int(key.replace('amount_', ''))
            amount = float(value) if value else 0
            if amount > 0:
                user_amounts[user_id] = amount
    
    if not user_amounts:
        flash(request, "Nenhum valor foi inserido para nenhum utilizador.", "warning")
        return RedirectResponse(url="/pagamentos/spend-prizes", status_code=302)
    
    # Call the updated spend_prizes_on_users with user_amounts
    result = spend_prizes_on_users(db, user_amounts=user_amounts)
    
    if result["distributed"] > 0:
        flash(request, f"Prémios distribuídos: {result['distributed']}€ para {result['users_paid']} utilizador(es). Restante na Caixa: {result['remaining_caixa']}€", "success")
    else:
        flash(request, "Não foi possível distribuir prémios (saldo insuficiente na Caixa).", "info")
    return RedirectResponse(url="/pagamentos", status_code=302)
