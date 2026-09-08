from __future__ import annotations

import asyncio
import time
from io import BytesIO

import jwt
import pytest
from fastapi import HTTPException, UploadFile

from app.api import import_router
from app.core.config import settings
from app.core.user_context import UserContext, _validate_supabase_user

SECRET = "a" * 32
ISSUER = "https://example.supabase.co/auth/v1"
USER_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture()
def supabase_jwt_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")


def _token(**claims: object) -> str:
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _valid_claims() -> dict[str, object]:
    return {
        "sub": USER_ID,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": ISSUER,
        "exp": int(time.time()) + 300,
    }


def test_local_jwt_fast_path_requires_supabase_claims(
    supabase_jwt_settings: None,
) -> None:
    token = _token(**_valid_claims())

    assert _validate_supabase_user(token) == USER_ID


@pytest.mark.parametrize(
    "claim, value",
    [
        ("exp", None),
        ("aud", "wrong-audience"),
        ("role", "service_role"),
        ("iss", "https://attacker.example/auth/v1"),
        ("sub", None),
    ],
)
def test_local_jwt_fast_path_rejects_missing_or_invalid_claims(
    supabase_jwt_settings: None,
    claim: str,
    value: object,
) -> None:
    claims = _valid_claims()
    if value is None:
        claims.pop(claim)
    else:
        claims[claim] = value
    token = _token(**claims)

    with pytest.raises(HTTPException) as exc_info:
        _validate_supabase_user(token)

    assert exc_info.value.status_code == 401


def test_upload_cap_rejects_reported_size_before_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_router, "MAX_UPLOAD_BYTES", 4)
    upload = UploadFile(file=BytesIO(b"1234"), filename="sample.csv", size=5)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(import_router._read_upload(upload))

    assert exc_info.value.status_code == 413


def test_upload_cap_rejects_actual_size_when_report_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(import_router, "MAX_UPLOAD_BYTES", 4)
    upload = UploadFile(file=BytesIO(b"12345"), filename="sample.csv")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(import_router._read_upload(upload))

    assert exc_info.value.status_code == 413


def test_upload_cap_reads_at_most_one_byte_past_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(import_router, "MAX_UPLOAD_BYTES", 4)

    class UploadProbe:
        size = None
        requested_size: int | None = None

        async def read(self, size: int = -1) -> bytes:
            self.requested_size = size
            return b"12345"

    upload = UploadProbe()
    with pytest.raises(HTTPException):
        asyncio.run(import_router._read_upload(upload))

    assert upload.requested_size == 5


def test_upload_cap_accepts_file_at_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_router, "MAX_UPLOAD_BYTES", 4)
    upload = UploadFile(file=BytesIO(b"1234"), filename="sample.csv")

    assert asyncio.run(import_router._read_upload(upload)) == b"1234"


def _job() -> dict[str, object]:
    return {
        "status": "done",
        "result": {"rows": []},
        "error": None,
        "filename": "sample.csv",
        "created_at": time.time(),
        "user_id": USER_ID,
    }


def test_import_job_is_only_visible_to_its_owner() -> None:
    job_id = "security-audit-job"
    import_router._jobs[job_id] = _job()
    try:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                import_router.get_import_job(
                    job_id,
                    UserContext("22222222-2222-4222-8222-222222222222", "supabase"),
                )
            )

        assert exc_info.value.status_code == 404
        result = asyncio.run(import_router.get_import_job(job_id, UserContext(USER_ID, "supabase")))
        assert result["result"] == {"rows": []}
    finally:
        import_router._jobs.pop(job_id, None)
