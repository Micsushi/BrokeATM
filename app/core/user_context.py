from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.models import UserOwnedMixin
from app.services.app_settings import ensure_app_settings
from app.services.starter_categories import seed_starter_categories

MOCK_USER_ID = "00000000-0000-4000-8000-000000000001"

# Per-process cache: avoids re-running seed SELECTs on every request.
# Serverless cold starts get an empty set — first request does 2 cheap SELECTs,
# subsequent warm invocations skip them. Correctness is guaranteed by the
# idempotent seed functions regardless.
_bootstrapped_users: set[str] = set()


@dataclass(frozen=True)
class UserContext:
    user_id: str | None
    mode: str

    @property
    def is_scoped(self) -> bool:
        return self.user_id is not None


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _validate_supabase_user(token: str) -> str:
    # Fast path: verify the JWT locally using the project secret (no network call).
    if settings.supabase_jwt_secret:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired auth session.") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=401, detail="Invalid or expired auth session.") from exc
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise HTTPException(status_code=401, detail="Invalid auth session.")
        return user_id

    # Slow path: call Supabase /auth/v1/user (no jwt secret configured).
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=500, detail="Supabase auth is not configured.")

    url = settings.supabase_url.rstrip("/") + "/auth/v1/user"
    try:
        response = httpx.get(
            url,
            headers={
                "apikey": settings.supabase_anon_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Could not validate auth session.") from exc

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or expired auth session.")
    if response.status_code >= 400:
        raise HTTPException(status_code=503, detail="Could not validate auth session.")

    payload = response.json()
    user_id = payload.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Invalid auth session.")
    return user_id


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> UserContext:
    if settings.auth_mode == "none" and not settings.is_cloud_mode:
        return UserContext(user_id=None, mode="local")
    if settings.auth_mode == "mock":
        return UserContext(user_id=MOCK_USER_ID, mode="mock")

    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return UserContext(user_id=_validate_supabase_user(token), mode="supabase")


def user_filter(model: type[UserOwnedMixin], user: UserContext) -> Any:
    if not user.is_scoped:
        return model.user_id.is_(None)
    return model.user_id == user.user_id


def assign_user(model: UserOwnedMixin, user: UserContext) -> None:
    if user.is_scoped:
        model.user_id = user.user_id


def require_owned_record(
    db: Session,
    model: type[UserOwnedMixin],
    row_id: int | None,
    user: UserContext,
    label: str,
) -> Any | None:
    if row_id is None:
        return None
    record = db.query(model).filter(model.id == row_id, user_filter(model, user)).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def get_db_for_user(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[UserContext, Depends(get_current_user)],
) -> Session:
    if user.is_scoped and user.user_id not in _bootstrapped_users:
        seed_starter_categories(db, user_id=user.user_id)
        ensure_app_settings(db, user_id=user.user_id)
        assert user.user_id is not None
        _bootstrapped_users.add(user.user_id)
    return db
