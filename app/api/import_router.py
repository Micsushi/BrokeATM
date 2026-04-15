from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import CommitRequest, CommitResponse, ParseResponse
from app.models.models import Category
from app.services.app_settings import get_default_currency
from app.services.csv_parser import parse_csv
from app.services.import_service import check_duplicates, commit_import
from app.services.keyword_matching import KeywordMatcher

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/parse", response_model=ParseResponse)
async def parse_upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Any:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    content = await file.read()
    keyword_matcher = KeywordMatcher.from_categories(db.query(Category).all())
    return parse_csv(
        content,
        default_currency=get_default_currency(db),
        keyword_matcher=keyword_matcher,
    )


@router.post("/check-duplicates")
async def check_dups(payload: dict[str, Any], db: Session = Depends(get_db)) -> Any:
    rows = payload.get("rows", [])
    return {"rows": check_duplicates(db, rows)}


@router.post("/commit", response_model=CommitResponse)
async def commit(request: CommitRequest, db: Session = Depends(get_db)) -> Any:
    rows_dicts = [r.model_dump() for r in request.rows]
    try:
        batches, total_imported, total_skipped = commit_import(
            db,
            rows=rows_dicts,
            filename=request.filename,
            month=request.month,
            year=request.year,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Import could not complete due to a database conflict. "
                "Try duplicate check again, or refresh and re-upload the file."
            ),
        ) from None
    ids = [b.id for b in batches]
    return CommitResponse(
        batch_id=ids[0] if ids else "",
        batch_ids=ids,
        imported=total_imported,
        skipped=total_skipped,
    )
