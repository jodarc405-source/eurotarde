from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import get_db
from services.payment_service import get_all_users_weeks

router = APIRouter()


@router.get("/semanas", response_class=HTMLResponse)
async def semanas_page(request: Request, db: Session = Depends(get_db)):
    weeks_data = get_all_users_weeks(db)

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
    })
