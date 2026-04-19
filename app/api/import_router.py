from __future__ import annotations

import asyncio
import functools
import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import CommitRequest, CommitResponse, ParseResponse, ParserResult
from app.models.models import Category
from app.services.app_settings import get_default_currency
from app.services.csv_parser import parse_csv
from app.services.import_service import check_duplicates, commit_import
from app.services.keyword_matching import KeywordMatcher
from app.services.parsers.registry import run_all

router = APIRouter(prefix="/api/import", tags=["import"])

_PDF_OFX_EXTS = {".pdf", ".ofx", ".qfx"}

_jobs: dict[str, dict] = {}
_JOB_TTL = 3600


def _prune_old_jobs() -> None:
    cutoff = time.time() - _JOB_TTL
    expired = [k for k, v in list(_jobs.items()) if v["created_at"] < cutoff]
    for k in expired:
        _jobs.pop(k, None)


async def _run_csv_job(job_id: str, content: bytes, filename: str, default_currency: str, keyword_matcher: Any) -> None:
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(parse_csv, content, default_currency=default_currency, keyword_matcher=keyword_matcher),
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = result.model_dump()
    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)


async def _run_pdf_job(job_id: str, content: bytes, filename: str, currency: str, keyword_matcher: Any, known_categories: list[str]) -> None:
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            functools.partial(run_all, content, filename, currency, keyword_matcher, known_categories),
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = [r.model_dump() for r in results]
    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)


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


@router.post("/parse-all", response_model=list[ParserResult])
async def parse_all_upload(file: UploadFile = File(...), db: Session = Depends(get_db)) -> Any:
    fname = (file.filename or "").lower()
    ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in _PDF_OFX_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .ofx, .qfx",
        )
    content = await file.read()
    cats = db.query(Category).all()
    keyword_matcher = KeywordMatcher.from_categories(cats)
    known_categories = [c.name for c in cats]
    currency = get_default_currency(db)
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        functools.partial(run_all, content, file.filename or "", currency, keyword_matcher, known_categories),
    )
    return results


@router.post("/parse-async")
async def parse_async_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)) -> Any:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    content = await file.read()
    keyword_matcher = KeywordMatcher.from_categories(db.query(Category).all())
    default_currency = get_default_currency(db)
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "result": None, "error": None, "filename": file.filename, "created_at": time.time()}
    _prune_old_jobs()
    background_tasks.add_task(_run_csv_job, job_id, content, file.filename, default_currency, keyword_matcher)
    return {"job_id": job_id, "filename": file.filename}


@router.post("/parse-all-async")
async def parse_all_async(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)) -> Any:
    fname = (file.filename or "").lower()
    ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in _PDF_OFX_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .ofx, .qfx")
    content = await file.read()
    cats = db.query(Category).all()
    keyword_matcher = KeywordMatcher.from_categories(cats)
    known_categories = [c.name for c in cats]
    currency = get_default_currency(db)
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "result": None, "error": None, "filename": file.filename, "created_at": time.time()}
    _prune_old_jobs()
    background_tasks.add_task(_run_pdf_job, job_id, content, file.filename or "", currency, keyword_matcher, known_categories)
    return {"job_id": job_id, "filename": file.filename}


@router.get("/job/{job_id}")
async def get_import_job(job_id: str) -> Any:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return {
        "job_id": job_id,
        "status": job["status"],
        "result": job["result"] if job["status"] == "done" else None,
        "error": job.get("error") if job["status"] == "error" else None,
        "filename": job["filename"],
    }


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
