from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from services.payment_service import get_all_users_weeks
from config import get_settings
from datetime import date

router = APIRouter()


@router.get("/semanas", response_class=HTMLResponse)
async def semanas_page(request: Request, db: Session = Depends(get_db)):
    weeks_data = get_all_users_weeks(db)
    settings = get_settings()
    week_value = getattr(settings, 'WEEK_VALUE', 1.0)
    current_year = date.today().year
    is_admin = request.session.get('is_admin', False)

    # Build month groups per user
    for uw in weeks_data:
        months = []
        cur_month = None
        group_start = 0
        for j, w in enumerate(uw['weeks']):
            if w['month'] != cur_month:
                if cur_month is not None:
                    months.append({'name': cur_month, 'span': j - group_start})
                cur_month = w['month']
                group_start = j
        if cur_month is not None:
            months.append({'name': cur_month, 'span': len(uw['weeks']) - group_start})
        uw['month_groups'] = months

    return request.app.state.templates.TemplateResponse("semanas/index.html", {
        "request": request,
        "weeks_data": weeks_data,
        "week_value": week_value,
        "current_year": current_year,
        "is_admin": is_admin,
    })


@router.post("/semanas/update-week-value")
async def update_week_value(request: Request, week_value: float = Form(...), db: Session = Depends(get_db)):
    """Update the week value setting (admin only)."""
    # Check admin permission
    if not request.session.get('is_admin', False):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Apenas administradores podem alterar o valor da semana.")
    
    from config import get_settings
    
    # Update the setting (this would need persistent storage, for now just in memory)
    # In production, you'd want to store this in a settings table or env var
    settings = get_settings()
    settings.WEEK_VALUE = max(0.01, week_value)
    
    return RedirectResponse(url="/semanas", status_code=302)
