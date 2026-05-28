from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.core.user_context import (
    UserContext,
    assign_user,
    get_current_user,
    get_db_for_user,
    user_filter,
)
from app.models.models import Category, Transaction
from app.services.keyword_matching import find_exact_keyword_conflicts, keywords_to_csv

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    return db.query(Category).filter(user_filter(Category, user)).order_by(Category.name).all()


@router.get("/stats")
def category_stats(
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    """Return each category with transaction count and total spend."""
    tx_user_cond = (
        Transaction.user_id == user.user_id
        if user.is_scoped
        else Transaction.user_id.is_(None)
    )
    rows = (
        db.query(
            Category.id,
            Category.name,
            Category.color,
            Category.keywords,
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(
            Transaction,
            and_(Transaction.category_id == Category.id, tx_user_cond),
        )
        .filter(user_filter(Category, user))
        .group_by(Category.id, Category.name, Category.color, Category.keywords)
        .order_by(Category.name)
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.name,
            "color": r.color,
            "keywords": r.keywords or "",
            "tx_count": r.tx_count or 0,
            "total": round(r.total or 0, 2),
        }
        for r in rows
    ]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    normalized_name = payload.name.strip().lower()
    existing = (
        db.query(Category)
        .filter(Category.name == normalized_name, user_filter(Category, user))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    normalized_keywords = keywords_to_csv((payload.keywords or "").split(","))
    exact_conflicts = find_exact_keyword_conflicts(
        db.query(Category).filter(user_filter(Category, user)).all(),
        (normalized_keywords or "").split(","),
    )
    if exact_conflicts:
        conflict = exact_conflicts[0]
        raise HTTPException(
            status_code=409,
            detail=(
                f'Keyword "{conflict["keyword"]}" already exists on '
                f'"{conflict["category_name"]}".'
            ),
        )
    data = payload.model_dump()
    data["name"] = normalized_name
    data["keywords"] = normalized_keywords
    cat = Category(**data)
    assign_user(cat, user)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/{cat_id}", response_model=CategoryOut)
def update_category(
    cat_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    cat = db.query(Category).filter(Category.id == cat_id, user_filter(Category, user)).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["name"] = updates["name"].strip().lower()
        existing = (
            db.query(Category)
            .filter(
                Category.name == updates["name"],
                Category.id != cat_id,
                user_filter(Category, user),
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Category already exists")
    if "keywords" in updates:
        updates["keywords"] = keywords_to_csv((updates["keywords"] or "").split(","))
        current_kws = set(filter(None, (cat.keywords or "").split(",")))
        current_kws = {k.strip() for k in current_kws}
        new_kws = set(filter(None, (updates["keywords"] or "").split(",")))
        new_kws = {k.strip() for k in new_kws}
        added_kws = new_kws - current_kws
        if added_kws:
            exact_conflicts = find_exact_keyword_conflicts(
                db.query(Category).filter(user_filter(Category, user)).all(),
                list(added_kws),
                exclude_category_id=cat_id,
            )
            if exact_conflicts:
                conflict = exact_conflicts[0]
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f'Keyword "{conflict["keyword"]}" already exists on '
                        f'"{conflict["category_name"]}".'
                    ),
                )
    for field, value in updates.items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}", status_code=204)
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> None:
    cat = db.query(Category).filter(Category.id == cat_id, user_filter(Category, user)).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
