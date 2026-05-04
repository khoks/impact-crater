"""impact-crater CLI entry point.

Starts the FastAPI server on a free localhost port and (by default)
opens the user's default browser to the local UI.

Usage:
    impact-crater                    # start server + open browser
    impact-crater --no-browser       # start server without opening browser
    impact-crater --port 9000        # request a specific port (errors if taken)
    impact-crater --host 127.0.0.1   # bind host (default: 127.0.0.1)
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from impact_crater import __version__

DEFAULT_HOST = "127.0.0.1"
PREFERRED_PORT = 8765


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.version:
        print(f"impact-crater {__version__}")
        return 0

    port = _choose_port(args.host, args.port)
    if port is None:
        print(
            f"impact-crater: requested port {args.port} is in use; pick another with --port",
            file=sys.stderr,
        )
        return 1

    url = f"http://{args.host}:{port}"
    print(f"impact-crater {__version__} starting on {url}")

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url,),
            daemon=True,
        ).start()

    uvicorn.run(
        "impact_crater.app:create_app",
        factory=True,
        host=args.host,
        port=port,
        log_level=args.log_level,
        reload=args.reload,
    )
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="impact-crater",
        description="Start the Impact Crater local server.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default: {DEFAULT_HOST})")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"bind port; if omitted, auto-pick (preferred: {PREFERRED_PORT})",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="do not open the default browser on start",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="uvicorn log level (default: info)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="enable uvicorn auto-reload (dev mode)",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    return parser.parse_args(argv)


def _choose_port(host: str, requested: int | None) -> int | None:
    """Return a usable port, or None if the user requested one that's taken."""
    if requested is not None:
        return requested if _port_is_free(host, requested) else None

    if _port_is_free(host, PREFERRED_PORT):
        return PREFERRED_PORT

    # Fall back to OS-assigned free port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return False
    return True


def _open_browser_when_ready(url: str, *, max_wait_s: float = 5.0) -> None:
    """Wait briefly for uvicorn to start accepting connections, then open the browser.

    Uvicorn binds the socket nearly-immediately, but giving it a beat avoids a
    race where the browser hits the URL before the server can respond.
    """
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        time.sleep(0.1)
        try:
            host, port = url.removeprefix("http://").split(":")
            with socket.create_connection((host, int(port)), timeout=0.2):
                break
        except OSError:
            continue
    webbrowser.open(url)


if __name__ == "__main__":
    sys.exit(main())
