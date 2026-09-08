from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from tempfile import SpooledTemporaryFile
from typing import Any

import pytest
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api import import_router
from app.core import request_limits


@pytest.fixture(autouse=True)
def isolated_job_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep process-global job state isolated between synthetic store checks."""

    with import_router._jobs_lock:
        import_router._jobs.clear()
    monkeypatch.setattr(import_router, "_retained_result_bytes", 0)
    yield
    with import_router._jobs_lock:
        import_router._jobs.clear()


def _scope(path: str, headers: list[tuple[bytes, bytes]] | None = None) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers or [],
        "http_version": "1.1",
        "scheme": "http",
        "query_string": b"",
        "client": ("test", 1234),
        "server": ("test", 80),
    }


def _run_asgi(
    app: Any,
    scope: dict[str, Any],
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    pending = iter(messages)

    async def receive() -> dict[str, Any]:
        try:
            return next(pending)
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent


def test_declared_oversize_is_rejected_before_inner_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(request_limits, "MAX_IMPORT_REQUEST_BYTES", 4)
    called = False

    async def inner(scope: dict[str, Any], receive: Any, send: Any) -> None:
        nonlocal called
        called = True

    middleware = request_limits.ImportRequestBodyLimitMiddleware(inner)
    sent = _run_asgi(
        middleware,
        _scope("/api/import/parse", [(b"content-length", b"5")]),
        [],
    )

    assert called is False
    assert sent[0]["status"] == 413


def test_streamed_oversize_without_content_length_stops_before_parser_receives_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(request_limits, "MAX_IMPORT_REQUEST_BYTES", 4)
    seen: list[bytes] = []

    async def parser(scope: dict[str, Any], receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            seen.append(message.get("body", b""))
            if not message.get("more_body", False):
                break

    middleware = request_limits.ImportRequestBodyLimitMiddleware(parser)
    sent = _run_asgi(
        middleware,
        _scope("/api/import/parse"),
        [
            {"type": "http.request", "body": b"1234", "more_body": True},
            {"type": "http.request", "body": b"5", "more_body": False},
        ],
    )

    assert seen == [b"1234"]
    assert sent[0]["status"] == 413


def test_fastapi_multipart_streamed_oversize_returns_413_before_parser_spooling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = FastAPI()
    closed_files = 0

    @api.post("/api/import/parse")
    async def parse(file: UploadFile = File(...)) -> dict[str, object]:
        return {"filename": file.filename}

    original_close = SpooledTemporaryFile.close

    def tracked_close(file: SpooledTemporaryFile) -> None:
        nonlocal closed_files
        closed_files += 1
        original_close(file)

    monkeypatch.setattr(SpooledTemporaryFile, "close", tracked_close)

    boundary = b"----brokeatm-test-boundary"
    body = (
        b"--"
        + boundary
        + b'\r\nContent-Disposition: form-data; name="file"; filename="sample.csv"\r\n'
        + b"Content-Type: text/csv\r\n\r\n1234\r\n--"
        + boundary
        + b"--\r\n"
    )
    split = body.find(b"\r\n\r\n") + 8
    monkeypatch.setattr(request_limits, "MAX_IMPORT_REQUEST_BYTES", 160)
    wrapped = request_limits.ImportRequestBodyLimitMiddleware(api)
    sent = _run_asgi(
        wrapped,
        _scope(
            "/api/import/parse",
            [(b"content-type", b"multipart/form-data; boundary=" + boundary)],
        ),
        [
            {"type": "http.request", "body": body[:split], "more_body": True},
            {"type": "http.request", "body": body[split:], "more_body": False},
        ],
    )

    assert len(body) > 160
    assert sent[0]["status"] == 413
    assert closed_files == 1


def test_multipart_upload_at_limit_reaches_fastapi_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    api = FastAPI()

    @api.post("/api/import/parse")
    async def parse(file: UploadFile = File(...)) -> dict[str, object]:
        body = await file.read()
        return {"filename": file.filename, "size": len(body)}

    monkeypatch.setattr(request_limits, "MAX_IMPORT_REQUEST_BYTES", 1024)
    wrapped = request_limits.ImportRequestBodyLimitMiddleware(api)
    with TestClient(wrapped) as client:
        response = client.post(
            "/api/import/parse",
            files={"file": ("sample.csv", b"1234", "text/csv")},
        )

    assert response.status_code == 200
    assert response.json() == {"filename": "sample.csv", "size": 4}


def test_pending_jobs_count_against_admission_limit_and_survive_ttl_prune(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(import_router, "MAX_ASYNC_JOBS", 1)
    monkeypatch.setattr(import_router, "_JOB_TTL", 0)
    import_router._jobs["pending"] = {
        "status": "pending",
        "created_at": time.time() - 10,
        "result_bytes": 0,
    }

    with pytest.raises(HTTPException) as exc_info:
        import_router._register_async_job("new.csv", "owner")

    assert getattr(exc_info.value, "status_code", None) == 429
    assert "pending" in import_router._jobs


def test_expired_terminal_job_frees_count_and_retained_result_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(import_router, "MAX_ASYNC_JOBS", 1)
    monkeypatch.setattr(import_router, "_JOB_TTL", 0)
    import_router._jobs["done"] = {
        "status": "done",
        "created_at": time.time() - 10,
        "result_bytes": 3,
    }
    import_router._retained_result_bytes = 3

    job_id = import_router._register_async_job("new.csv", "owner")

    assert job_id in import_router._jobs
    assert "done" not in import_router._jobs
    assert import_router._retained_result_bytes == 0


def test_result_retention_counts_compact_serialized_utf8_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(import_router, "MAX_ASYNC_RESULT_BYTES", 20)
    job_id = import_router._register_async_job("sample.csv", "owner")
    result = {"message": "café"}

    import_router._store_job_result(job_id, result)

    expected_bytes = len(b'{"message":"caf\xc3\xa9"}')
    assert import_router._jobs[job_id]["status"] == "done"
    assert import_router._jobs[job_id]["result_bytes"] == expected_bytes
    assert import_router._retained_result_bytes == expected_bytes


def test_result_budget_and_retained_metadata_are_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_router, "MAX_ASYNC_RESULT_BYTES", 4)
    job_id = import_router._register_async_job("😀" * 1000, "owner")
    import_router._store_job_result(job_id, {"value": "too large"})
    import_router._store_job_error(job_id, "é" * 10000)

    job = import_router._jobs[job_id]
    assert job["status"] == "error"
    assert job["result"] is None
    assert len(str(job["filename"]).encode("utf-8")) <= import_router.MAX_ASYNC_FILENAME_BYTES
    assert len(str(job["error"]).encode("utf-8")) <= import_router.MAX_ASYNC_ERROR_BYTES
    assert import_router._retained_result_bytes == 0


def test_late_completion_does_not_recreate_evicted_job() -> None:
    job_id = import_router._register_async_job("sample.csv", "owner")
    import_router._jobs.pop(job_id)

    import_router._store_job_result(job_id, {"rows": []})
    import_router._store_job_error(job_id, "late failure")

    assert job_id not in import_router._jobs


def test_main_registers_request_limit_middleware_in_isolated_cloud_import() -> None:
    # Importing app.main performs local schema setup/OCR prewarm, so verify registration
    # in a subprocess with cloud mode and isolated filesystem settings.
    isolated = tempfile.mkdtemp(prefix="brokeatm-main-import-")
    env = {
        **os.environ,
        "ATM_DEPLOYMENT_MODE": "cloud",
        "ATM_DATABASE_BACKEND": "sqlite",
        "ATM_DATA_DIR": isolated,
        "HOME": isolated,
        "USERPROFILE": isolated,
        "APPDATA": isolated,
        "LOCALAPPDATA": isolated,
        "XDG_CONFIG_HOME": isolated,
    }
    check = (
        "import app.main; "
        "print(any(m.cls.__name__ == 'ImportRequestBodyLimitMiddleware' "
        "for m in app.main.app.user_middleware))"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            check,
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "True"
