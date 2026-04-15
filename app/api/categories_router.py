from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.models.models import Category, Transaction
from app.services.keyword_matching import find_exact_keyword_conflicts, keywords_to_csv

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> Any:
    return db.query(Category).order_by(Category.name).all()


@router.get("/stats")
def category_stats(db: Session = Depends(get_db)) -> Any:
    """Return each category with transaction count and total spend."""
    rows = (
        db.query(
            Category.id,
            Category.name,
            Category.color,
            Category.keywords,
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.amount).label("total"),
        )
        .outerjoin(Transaction, Transaction.category_id == Category.id)
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
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)) -> Any:
    normalized_name = payload.name.strip().lower()
    existing = db.query(Category).filter(Category.name == normalized_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    normalized_keywords = keywords_to_csv((payload.keywords or "").split(","))
    exact_conflicts = find_exact_keyword_conflicts(
        db.query(Category).all(),
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
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, payload: CategoryUpdate, db: Session = Depends(get_db)) -> Any:
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        updates["name"] = updates["name"].strip().lower()
        existing = (
            db.query(Category)
            .filter(Category.name == updates["name"], Category.id != cat_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=409, detail="Category already exists")
    if "keywords" in updates:
        updates["keywords"] = keywords_to_csv((updates["keywords"] or "").split(","))
        exact_conflicts = find_exact_keyword_conflicts(
            db.query(Category).all(),
            (updates["keywords"] or "").split(","),
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
def delete_category(cat_id: int, db: Session = Depends(get_db)) -> None:
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
