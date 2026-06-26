"""Desktop launcher for the JARVIS FastAPI dashboard."""

from __future__ import annotations

import argparse
import contextlib
import multiprocessing
import queue
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass

import uvicorn

APP_TITLE = "JARVIS"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820
WINDOW_MIN_WIDTH = 960
WINDOW_MIN_HEIGHT = 640


@dataclass
class DesktopServer:
    server: uvicorn.Server
    thread: threading.Thread
    url: str
    errors: "queue.Queue[BaseException]"


def _port_is_available(host: str, port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _find_available_port(host: str, preferred_port: int) -> int:
    if _port_is_available(host, preferred_port):
        return preferred_port

    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _wait_for_server(
    url: str,
    thread: threading.Thread,
    errors: "queue.Queue[BaseException]",
    timeout_seconds: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: BaseException | None = None

    while time.monotonic() < deadline:
        if not thread.is_alive():
            if not errors.empty():
                raise RuntimeError("Jarvis sunucusu baslatilamadi.") from errors.get()
            raise RuntimeError("Jarvis sunucusu baslamadan kapandi.")

        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
            time.sleep(0.2)

    raise TimeoutError(f"Jarvis sunucusu zamaninda hazir olmadi: {url}") from last_error


def start_server(host: str, port: int) -> DesktopServer:
    from app.api import app as api_app

    selected_port = _find_available_port(host, port)
    url = f"http://{host}:{selected_port}"
    errors: "queue.Queue[BaseException]" = queue.Queue()

    config = uvicorn.Config(
        api_app,
        host=host,
        port=selected_port,
        reload=False,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def run_server() -> None:
        try:
            server.run()
        except BaseException as exc:
            errors.put(exc)
            raise

    thread = threading.Thread(target=run_server, name="jarvis-web-server", daemon=True)
    thread.start()
    _wait_for_server(url, thread, errors)
    return DesktopServer(server=server, thread=thread, url=url, errors=errors)


def stop_server(desktop_server: DesktopServer) -> None:
    desktop_server.server.should_exit = True
    desktop_server.thread.join(timeout=3)


def open_browser_fallback(url: str) -> None:
    webbrowser.open(url)
    print(f"JARVIS calisiyor: {url}")
    print("Kapatmak icin Ctrl+C kullanin.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def run_desktop_window(url: str, debug: bool = False) -> None:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "pywebview kurulu degil. Kurulum: ./venv/bin/python -m pip install pywebview"
        ) from exc

    webview.create_window(
        APP_TITLE,
        url,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        min_size=(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT),
        resizable=True,
        text_select=True,
        background_color="#131318",
    )
    webview.start(debug=debug)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JARVIS masaustu uygulamasini baslatir.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Yerel web sunucusu host adresi.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Tercih edilen yerel port.")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Native pencere yerine varsayilan tarayicida ac.",
    )
    parser.add_argument(
        "--debug-webview",
        action="store_true",
        help="pywebview debug modunu ac.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    args = parse_args(argv)
    desktop_server: DesktopServer | None = None

    try:
        desktop_server = start_server(args.host, args.port)
        if args.browser:
            open_browser_fallback(desktop_server.url)
        else:
            run_desktop_window(desktop_server.url, debug=args.debug_webview)
        return 0
    except RuntimeError as exc:
        if desktop_server is not None and not args.browser:
            print(exc, file=sys.stderr)
            open_browser_fallback(desktop_server.url)
            return 0
        print(exc, file=sys.stderr)
        return 1
    finally:
        if desktop_server is not None:
            stop_server(desktop_server)


if __name__ == "__main__":
    raise SystemExit(main())
