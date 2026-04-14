from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.schemas import ProcessRecurringResponse, RecurringRuleCreate, RecurringRuleOut
from app.models.models import RecurringRule
from app.services.recurring_service import process_due_rules

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


def get_db():
    with SessionLocal() as db:
        yield db


@router.get("", response_model=list[RecurringRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(RecurringRule).order_by(RecurringRule.created_at.desc()).all()


@router.post("", response_model=RecurringRuleOut, status_code=201)
def create_rule(payload: RecurringRuleCreate, db: Session = Depends(get_db)):
    rule = RecurringRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(RecurringRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/process", response_model=ProcessRecurringResponse)
def process_recurring(db: Session = Depends(get_db)):
    return process_due_rules(db)
