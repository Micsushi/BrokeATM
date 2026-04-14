from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.schemas import AppSettingsOut, AppSettingsUpdate
from app.services.app_settings import ensure_app_settings, update_default_currency

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> AppSettingsOut:
    settings = ensure_app_settings(db)
    return AppSettingsOut.model_validate(settings)


@router.put("", response_model=AppSettingsOut)
def put_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)) -> AppSettingsOut:
    try:
        settings = update_default_currency(db, payload.default_currency)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AppSettingsOut.model_validate(settings)
