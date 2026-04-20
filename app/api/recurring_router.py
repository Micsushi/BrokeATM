from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import (
    ProcessRecurringResponse,
    RecurringDeleteFromRequest,
    RecurringRuleCreate,
    RecurringRuleOut,
    RecurringRuleUpdate,
)
from app.models.models import Account, Category, RecurringRule, Transaction
from app.services.recurring_service import (
    apply_rule_update,
    delete_rule_and_all_transactions,
    delete_rule_transactions_from,
    preview_rule_update,
    process_due_rules,
)

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


def _enrich(rule: RecurringRule, db: Session) -> RecurringRuleOut:
    out = RecurringRuleOut.model_validate(rule)
    if rule.category_id:
        cat = db.get(Category, rule.category_id)
        out.category_name = cat.name if cat else None
    if rule.account_id:
        acc = db.get(Account, rule.account_id)
        out.account_name = acc.name if acc else None
    out.transaction_count = db.query(Transaction).filter(
        Transaction.recurring_rule_id == rule.id
    ).count()
    return out


def _validate_rule_window(start_date, end_date) -> None:
    if end_date is not None and end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date must be on or after the start date.",
        )


@router.get("", response_model=list[RecurringRuleOut])
def list_rules(db: Session = Depends(get_db)):
    rules = db.query(RecurringRule).order_by(RecurringRule.start_date.desc()).all()
    return [_enrich(r, db) for r in rules]


@router.post("", response_model=RecurringRuleOut, status_code=201)
def create_rule(payload: RecurringRuleCreate, db: Session = Depends(get_db)):
    _validate_rule_window(payload.start_date, payload.end_date)
    rule = RecurringRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    # generate all entries up to today immediately
    process_due_rules(db)
    db.refresh(rule)
    return _enrich(rule, db)


@router.patch("/{rule_id}", response_model=RecurringRuleOut)
def update_rule(rule_id: int, payload: RecurringRuleUpdate, db: Session = Depends(get_db)):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    fields = payload.model_dump(
        exclude_unset=True,
        exclude={
            "keep_overlap",
            "force_remove_overlap",
            "backfill_missing",
            "skip_backfill",
        },
    )

    next_start = fields.get("start_date", rule.start_date)
    next_end = fields.get("end_date", rule.end_date)
    _validate_rule_window(next_start, next_end)

    impact = preview_rule_update(db, rule, fields)
    needs_overlap_choice = impact["overlap_count"] > 0 and not (
        payload.keep_overlap or payload.force_remove_overlap
    )
    needs_backfill_choice = impact["missing_count"] > 0 and not (
        payload.backfill_missing or payload.skip_backfill
    )

    if impact["schedule_changed"] and (needs_overlap_choice or needs_backfill_choice):
        detail = {
            "needs_confirmation": True,
            "overlap_count": impact["overlap_count"],
            "missing_count": impact["missing_count"],
            "message": "This schedule change affects existing recurring entries.",
        }
        if impact["overlap_count"] > 0:
            detail["overlap_message"] = (
                f"{impact['overlap_count']} existing entr"
                f"{'y falls' if impact['overlap_count'] == 1 else 'ies fall'} "
                "outside the new schedule."
            )
        if impact["missing_count"] > 0:
            detail["missing_message"] = (
                f"{impact['missing_count']} scheduled entr"
                f"{'y is' if impact['missing_count'] == 1 else 'ies are'} missing and can be added."
            )
        raise HTTPException(status_code=409, detail=detail)

    apply_rule_update(
        db,
        rule,
        fields,
        remove_overlap=payload.force_remove_overlap,
        backfill_missing=payload.backfill_missing,
    )
    return _enrich(rule, db)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    delete_rule_and_all_transactions(db, rule)


@router.post("/{rule_id}/delete-from", status_code=200)
def delete_from_date(
    rule_id: int,
    payload: RecurringDeleteFromRequest,
    db: Session = Depends(get_db),
):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    deleted = delete_rule_transactions_from(db, rule, payload.from_date)
    return {"deleted": deleted}


@router.post("/process", response_model=ProcessRecurringResponse)
def process_recurring(db: Session = Depends(get_db)):
    return process_due_rules(db)
