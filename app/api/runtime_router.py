from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/config")
def runtime_config() -> dict[str, str | bool | None]:
    return {
        "deployment_mode": settings.deployment_mode,
        "auth_mode": settings.auth_mode,
        "csv_only_imports": settings.csv_only_imports,
        "supabase_url": settings.supabase_url if settings.is_cloud_mode else None,
        "supabase_anon_key": settings.supabase_anon_key if settings.is_cloud_mode else None,
        "site_url": settings.site_url,
    }
