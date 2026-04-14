from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import BudgetSave, BudgetSummaryResponse
from app.services.budget_service import (
    get_monthly_summary,
    get_settings_with_averages,
    save_budget_rules,
)

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("/settings")
def budget_settings(avg_months: int = 3, db: Session = Depends(get_db)):
    return get_settings_with_averages(db, avg_months)


@router.put("/settings", status_code=200)
def save_budget(payload: BudgetSave, db: Session = Depends(get_db)):
    try:
        save_budget_rules(
            db,
            total=payload.total,
            rules=[r.model_dump() for r in payload.rules],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/summary", response_model=BudgetSummaryResponse)
def budget_summary(months: int = 6, db: Session = Depends(get_db)):
    return get_monthly_summary(db, months)
