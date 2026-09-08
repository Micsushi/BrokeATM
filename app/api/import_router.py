from __future__ import annotations

import asyncio
import functools
import json
import time
import uuid
from threading import RLock
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.schemas import CommitRequest, CommitResponse, ParseResponse, ParserResult
from app.core.user_context import UserContext, get_current_user, get_db_for_user, user_filter
from app.models.models import Category
from app.services.app_settings import get_default_currency
from app.services.csv_parser import parse_csv
from app.services.import_service import check_duplicates, commit_import
from app.services.keyword_matching import KeywordMatcher

router = APIRouter(prefix="/api/import", tags=["import"])

_PDF_OFX_EXTS = {".pdf", ".ofx", ".qfx"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ASYNC_JOBS = 32
MAX_ASYNC_RESULT_BYTES = 4 * 1024 * 1024
MAX_ASYNC_FILENAME_BYTES = 1024
MAX_ASYNC_ERROR_BYTES = 8 * 1024

_jobs: dict[str, dict] = {}
_jobs_lock = RLock()
_retained_result_bytes = 0
_JOB_TTL = 3600


async def _read_upload(file: UploadFile) -> bytes:
    reported_size = file.size
    if reported_size is not None and reported_size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")
    return content


def _truncate_utf8(value: object, max_bytes: int) -> str:
    text = str(value)
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _serialize_result(result: object) -> bytes:
    return json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _prune_old_jobs() -> None:
    global _retained_result_bytes

    cutoff = time.time() - _JOB_TTL
    with _jobs_lock:
        expired = [
            k
            for k, v in list(_jobs.items())
            if v.get("status") in {"done", "error"} and v["created_at"] < cutoff
        ]
        for k in expired:
            job = _jobs.pop(k, None)
            if job:
                _retained_result_bytes -= int(job.get("result_bytes", 0) or 0)


def _register_async_job(filename: str, user_id: str | None) -> str:
    _prune_old_jobs()
    with _jobs_lock:
        if len(_jobs) >= MAX_ASYNC_JOBS:
            raise HTTPException(
                status_code=429,
                detail="Too many asynchronous imports are already queued.",
            )
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {
            "status": "pending",
            "result": None,
            "result_bytes": 0,
            "error": None,
            "filename": _truncate_utf8(filename, MAX_ASYNC_FILENAME_BYTES),
            "created_at": time.time(),
            "user_id": user_id,
        }
        return job_id


def _store_job_error(job_id: str, error: object) -> None:
    global _retained_result_bytes

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        _retained_result_bytes -= int(job.get("result_bytes", 0) or 0)
        job["status"] = "error"
        job["result"] = None
        job["result_bytes"] = 0
        job["error"] = _truncate_utf8(error, MAX_ASYNC_ERROR_BYTES)


def _store_job_result(job_id: str, result: object) -> None:
    global _retained_result_bytes

    try:
        encoded = _serialize_result(result)
    except (TypeError, ValueError, OverflowError):
        _store_job_error(job_id, "Import result could not be retained.")
        return

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        if (
            len(encoded) > MAX_ASYNC_RESULT_BYTES
            or _retained_result_bytes + len(encoded) > MAX_ASYNC_RESULT_BYTES
        ):
            job["status"] = "error"
            job["result"] = None
            job["result_bytes"] = 0
            job["error"] = "Import result exceeded the retention budget."
            return
        job["status"] = "done"
        job["result"] = result
        job["result_bytes"] = len(encoded)
        job["error"] = None
        _retained_result_bytes += len(encoded)


async def _run_csv_job(
    job_id: str,
    content: bytes,
    filename: str,
    default_currency: str,
    keyword_matcher: Any,
) -> None:
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            functools.partial(
                parse_csv,
                content,
                default_currency=default_currency,
                keyword_matcher=keyword_matcher,
            ),
        )
        _store_job_result(job_id, result)
    except Exception as exc:
        _store_job_error(job_id, exc)


async def _run_pdf_job(
    job_id: str,
    content: bytes,
    filename: str,
    currency: str,
    keyword_matcher: Any,
    known_categories: list[str],
) -> None:
    try:
        from app.services.parsers.registry import run_all

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            functools.partial(
                run_all,
                content,
                filename,
                currency,
                keyword_matcher,
                known_categories,
            ),
        )
        _store_job_result(job_id, results)
    except Exception as exc:
        _store_job_error(job_id, exc)


@router.post("/parse", response_model=ParseResponse)
async def parse_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    content = await _read_upload(file)
    keyword_matcher = KeywordMatcher.from_categories(
        db.query(Category).filter(user_filter(Category, user)).all()
    )
    return parse_csv(
        content,
        default_currency=get_default_currency(db, user_id=user.user_id),
        keyword_matcher=keyword_matcher,
    )


@router.post("/parse-all", response_model=list[ParserResult])
async def parse_all_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if settings.csv_only_imports:
        raise HTTPException(status_code=400, detail="Online mode supports CSV import only.")
    from app.services.parsers.registry import run_all

    fname = (file.filename or "").lower()
    ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in _PDF_OFX_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .ofx, .qfx",
        )
    content = await _read_upload(file)
    cats = db.query(Category).filter(user_filter(Category, user)).all()
    keyword_matcher = KeywordMatcher.from_categories(cats)
    known_categories = [c.name for c in cats]
    currency = get_default_currency(db, user_id=user.user_id)
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        functools.partial(
            run_all,
            content,
            file.filename or "",
            currency,
            keyword_matcher,
            known_categories,
        ),
    )
    return results


@router.post("/parse-async")
async def parse_async_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    content = await _read_upload(file)
    keyword_matcher = KeywordMatcher.from_categories(
        db.query(Category).filter(user_filter(Category, user)).all()
    )
    default_currency = get_default_currency(db, user_id=user.user_id)
    job_id = _register_async_job(file.filename, user.user_id)
    background_tasks.add_task(
        _run_csv_job,
        job_id,
        content,
        file.filename,
        default_currency,
        keyword_matcher,
    )
    return {"job_id": job_id, "filename": file.filename}


@router.post("/parse-all-async")
async def parse_all_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    if settings.csv_only_imports:
        raise HTTPException(status_code=400, detail="Online mode supports CSV import only.")
    fname = (file.filename or "").lower()
    ext = "." + fname.rsplit(".", 1)[-1] if "." in fname else ""
    if ext not in _PDF_OFX_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .ofx, .qfx",
        )
    content = await _read_upload(file)
    cats = db.query(Category).filter(user_filter(Category, user)).all()
    keyword_matcher = KeywordMatcher.from_categories(cats)
    known_categories = [c.name for c in cats]
    currency = get_default_currency(db, user_id=user.user_id)
    job_id = _register_async_job(file.filename, user.user_id)
    background_tasks.add_task(
        _run_pdf_job,
        job_id,
        content,
        file.filename or "",
        currency,
        keyword_matcher,
        known_categories,
    )
    return {"job_id": job_id, "filename": file.filename}


@router.get("/job/{job_id}")
async def get_import_job(
    job_id: str,
    user: UserContext = Depends(get_current_user),
) -> Any:
    _prune_old_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job.get("user_id") != user.user_id:
            raise HTTPException(status_code=404, detail="Job not found or expired.")
        status = job["status"]
        return {
            "job_id": job_id,
            "status": status,
            "result": job["result"] if status == "done" else None,
            "error": job.get("error") if status == "error" else None,
            "filename": job["filename"],
        }


@router.post("/check-duplicates")
async def check_dups(
    payload: dict[str, Any],
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    rows = payload.get("rows", [])
    return {"rows": check_duplicates(db, rows, user_id=user.user_id)}


@router.post("/commit", response_model=CommitResponse)
async def commit(
    request: CommitRequest,
    db: Session = Depends(get_db_for_user),
    user: UserContext = Depends(get_current_user),
) -> Any:
    rows_dicts = [r.model_dump() for r in request.rows]
    try:
        batches, total_imported, total_skipped = commit_import(
            db,
            rows=rows_dicts,
            filename=request.filename,
            month=request.month,
            year=request.year,
            user_id=user.user_id,
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
