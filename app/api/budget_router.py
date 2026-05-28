from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.schemas import BudgetSave, BudgetSummaryResponse
from app.core.user_context import (
    UserContext,
    get_current_user,
    get_db_for_user,
    require_owned_record,
)
from app.models.models import Category
from app.services.budget_service import (
    get_monthly_summary,
    get_settings_with_averages,
    save_budget_rules,
)

router = APIRouter(prefix="/api/budget", tags=["budget"])


def _category_id_from_budget_key(category_key: str) -> int | None:
    if not category_key.startswith("cat:"):
        return None
    try:
        return int(category_key.split(":", 1)[1])
    except ValueError:
        return None


def _validate_budget_category_ids(
    db: Session,
    payload: BudgetSave,
    user: UserContext,
) -> None:
    category_ids = {rule.category_id for rule in payload.rules}
    category_ids.update(
        category_id
        for category_id in (
            _category_id_from_budget_key(key) for key in payload.hidden_category_keys
        )
        if category_id is not None
    )
    for category_id in sorted(category_ids):
        require_owned_record(db, Category, category_id, user, "Category")


@router.get("/settings")
def budget_settings(
    avg_months: int = 3,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
):
    return get_settings_with_averages(db, avg_months, user_id=user.user_id)


@router.put("/settings", status_code=200)
def save_budget(
    payload: BudgetSave,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
):
    _validate_budget_category_ids(db, payload, user)
    try:
        save_budget_rules(
            db,
            total=payload.total,
            rules=[r.model_dump() for r in payload.rules],
            hidden_category_keys=payload.hidden_category_keys,
            user_id=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.get("/summary", response_model=BudgetSummaryResponse)
def budget_summary(
    months: int = 6,
    from_ym: str | None = None,
    to_ym: str | None = None,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
):
    return get_monthly_summary(
        db,
        months=months,
        from_ym=from_ym,
        to_ym=to_ym,
        user_id=user.user_id,
    )
