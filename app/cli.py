from __future__ import annotations

import argparse
import errno
import sys
import webbrowser
from threading import Timer


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="atm",
        description="BrokeATM: personal budget tracker",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser automatically")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    if not args.no_browser:
        Timer(1.5, webbrowser.open, args=[url]).start()

    print(f"BrokeATM starting at {url}")
    print("Press Ctrl+C to stop.\n")

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed. Run: pip install brokeatm", file=sys.stderr)
        sys.exit(1)

    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
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
                f"  atm --port 8001",
                file=sys.stderr,
            )
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
