from __future__ import annotations

import argparse
import errno
import sys
import time
import webbrowser
from pathlib import PureWindowsPath
from threading import Thread
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def _program_name() -> str:
    if getattr(sys, "frozen", False):
        return PureWindowsPath(sys.executable).stem or "BrokeATM"
    return "atm"


def _reload_enabled(requested: bool) -> bool:
    return requested and not getattr(sys, "frozen", False)


def _browser_host(host: str) -> str:
    normalized = (host or "").strip()
    if normalized in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized


def _wait_for_app(url: str, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1.0) as response:
                body = response.read(4096).decode("utf-8", errors="ignore")
                if response.status < 500 and "BrokeATM" in body:
                    return True
        except (OSError, URLError):
            time.sleep(0.25)
    return False


def _open_browser_when_ready(host: str, port: int) -> None:
    browser_host = _browser_host(host)
    url = f"http://{browser_host}:{port}"
    if _wait_for_app(url):
        webbrowser.open(url)


def _uvicorn_app_target(reload_enabled: bool) -> Any:
    if reload_enabled:
        return "app.main:app"

    # Import the ASGI app directly in normal runs so frozen builds do not depend
    # on a string-based module lookup at startup.
    from app.main import app

    return app


def main() -> None:
    prog = _program_name()
    parser = argparse.ArgumentParser(
        prog=prog,
        description="BrokeATM: personal budget tracker",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()
    reload_enabled = _reload_enabled(args.reload)
    browser_url = f"http://{_browser_host(args.host)}:{args.port}"

    if not args.no_browser:
        Thread(
            target=_open_browser_when_ready,
            args=(args.host, args.port),
            daemon=True,
        ).start()

    print(f"BrokeATM starting at {browser_url}")
    if getattr(sys, "frozen", False):
        print("Your browser will open automatically.")
        print("Keep this window open — closing it will stop BrokeATM.")
        print("Press Ctrl+C or close this window to quit.\n")
    else:
        print("Press Ctrl+C to stop.\n")

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Run: pip install brokeatm", file=sys.stderr)
        sys.exit(1)

    if args.reload and not reload_enabled:
        print("--reload is not available in the packaged app; starting without reload.\n")

    try:
        uvicorn.run(
            _uvicorn_app_target(reload_enabled),
            host=args.host,
            port=args.port,
            reload=reload_enabled,
        )
    except OSError as e:
        addr_in_use = (
            getattr(e, "winerror", None) == 10048
            or e.errno == errno.EADDRINUSE
            or e.errno == 10048
        )
        if addr_in_use:
            print(
                f"Port {args.port} is already in use (another BrokeATM or app is using it).\n"
                f"Fix: close that process, or start on a different port, for example:\n"
                f"  {prog} --port 8001",
                file=sys.stderr,
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
