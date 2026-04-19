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
    count_transactions_after,
    delete_rule_and_all_transactions,
    delete_rule_transactions_from,
    process_due_rules,
    remove_transactions_after,
    update_rule_and_transactions,
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


@router.get("", response_model=list[RecurringRuleOut])
def list_rules(db: Session = Depends(get_db)):
    rules = db.query(RecurringRule).order_by(RecurringRule.start_date.desc()).all()
    return [_enrich(r, db) for r in rules]


@router.post("", response_model=RecurringRuleOut, status_code=201)
def create_rule(payload: RecurringRuleCreate, db: Session = Depends(get_db)):
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

    fields = payload.model_dump(exclude_unset=True, exclude={"keep_overlap", "force_remove_overlap"})

    if "end_date" in fields and fields["end_date"] is not None:
        new_end = fields["end_date"]
        overlap_count = count_transactions_after(db, rule_id, new_end)
        if overlap_count > 0 and not payload.keep_overlap and not payload.force_remove_overlap:
            raise HTTPException(
                status_code=409,
                detail={
                    "overlap_count": overlap_count,
                    "message": f"{overlap_count} existing transaction(s) fall after the new end date.",
                },
            )
        if overlap_count > 0 and payload.force_remove_overlap:
            remove_transactions_after(db, rule_id, new_end)
            if rule.last_created_date and rule.last_created_date > new_end:
                rule.last_created_date = new_end

    update_rule_and_transactions(db, rule, fields)
    return _enrich(rule, db)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    delete_rule_and_all_transactions(db, rule)


@router.post("/{rule_id}/delete-from", status_code=200)
def delete_from_date(rule_id: int, payload: RecurringDeleteFromRequest, db: Session = Depends(get_db)):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    deleted = delete_rule_transactions_from(db, rule, payload.from_date)
    return {"deleted": deleted}


@router.post("/process", response_model=ProcessRecurringResponse)
def process_recurring(db: Session = Depends(get_db)):
    return process_due_rules(db)
