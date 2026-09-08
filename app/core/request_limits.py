from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse

MAX_IMPORT_REQUEST_BYTES = 26 * 1024 * 1024
IMPORT_UPLOAD_PATHS = frozenset(
    {
        "/api/import/parse",
        "/api/import/parse-all",
        "/api/import/parse-async",
        "/api/import/parse-all-async",
    }
)


class ImportRequestBodyLimitMiddleware:
    """Reject oversized import bodies before Starlette parses multipart uploads."""

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in IMPORT_UPLOAD_PATHS
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or ())
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                reported_size = int(content_length)
            except (TypeError, ValueError):
                reported_size = None
            if reported_size is not None and reported_size > MAX_IMPORT_REQUEST_BYTES:
                await JSONResponse(
                    {"detail": "Uploaded request body is too large."},
                    status_code=413,
                )(scope, receive, send)
                return

        received = 0
        oversized = False
        response_started = False

        async def limited_receive() -> dict[str, Any]:
            nonlocal received, oversized
            if oversized:
                return {"type": "http.disconnect"}
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body") or b"")
                if received > MAX_IMPORT_REQUEST_BYTES:
                    oversized = True
                    return {"type": "http.disconnect"}
            return message

        async def limited_send(message: dict[str, Any]) -> None:
            nonlocal response_started
            if oversized:
                return
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        finally:
            if oversized and not response_started:
                await JSONResponse(
                    {"detail": "Uploaded request body is too large."},
                    status_code=413,
                )(scope, receive, send)
