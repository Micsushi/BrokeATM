from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.schemas import AccountCreate, AccountOut
from app.core.user_context import (
    UserContext,
    assign_user,
    get_current_user,
    get_db_for_user,
    user_filter,
)
from app.models.models import Account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    return db.query(Account).filter(user_filter(Account, user)).order_by(Account.name).all()


@router.post("", response_model=AccountOut, status_code=201)
def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    acc = Account(**payload.model_dump())
    assign_user(acc, user)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.delete("/{acc_id}", status_code=204)
def delete_account(
    acc_id: int,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> None:
    acc = db.query(Account).filter(Account.id == acc_id, user_filter(Account, user)).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
