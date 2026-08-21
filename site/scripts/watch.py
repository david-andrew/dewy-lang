"""Rebuild the site when sources change, and keep serving ``site/dist``."""

from __future__ import annotations

import shutil
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build

PORT = 9000
POLL = 0.4
SKIP_DIRS = {".git", "__pycache__", "book", "dist", "designs"}
WATCH = [build.STATIC, build.LEARN, build.REFERENCE, build.PLAYGROUND_SOURCE, build.INSTALL_SCRIPT]
RELOAD_SNIPPET = (
    b'<script>(()=>{const e=new EventSource("/__watch__/events");'
    b"e.onmessage=()=>location.reload()})()</script>"
)


def snapshot(paths: list[Path]) -> dict[Path, tuple[int, int]]:
    out: dict[Path, tuple[int, int]] = {}
    for root in paths:
        if root.is_file():
            stat = root.stat()
            out[root] = (stat.st_mtime_ns, stat.st_size)
            continue
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            stat = path.stat()
            out[path] = (stat.st_mtime_ns, stat.st_size)
    return out


def sync_static() -> None:
    build.DIST.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        build.STATIC,
        build.DIST,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("designs"),
    )
    (build.DIST / ".nojekyll").write_text("")
    build.copy_install_script()


def rebuild(changed: set[Path]) -> None:
    mdbook = build.require_tool("mdbook")
    sync_static()
    build.build_book(build.LEARN, build.DIST / "learn", mdbook)
    build.build_book(build.REFERENCE, build.DIST / "reference", mdbook)
    if build.PLAYGROUND_SOURCE in changed:
        build.require_tool("wat2wasm")
        build.build_playground()
    build.write_sitemap()
    print(f"rebuilt {build.DIST}", flush=True)


class Reload:
    def __init__(self) -> None:
        self.gen = 0
        self.cond = threading.Condition()

    def bump(self) -> None:
        with self.cond:
            self.gen += 1
            self.cond.notify_all()

    def wait_after(self, seen: int) -> None:
        with self.cond:
            while self.gen <= seen:
                self.cond.wait()


reload = Reload()


def inject_reload(data: bytes) -> bytes:
    marker = b"</body>"
    index = data.lower().rfind(marker)
    if index == -1:
        return data + RELOAD_SNIPPET
    return data[:index] + RELOAD_SNIPPET + data[index:]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/__watch__/events":
            self._sse()
            return
        html = self._html_file()
        if html is not None:
            self._send_html(html, 200)
            return
        if self._existing_file() is None:
            fallback = build.DIST / "404.html"
            if fallback.is_file():
                self._send_html(fallback, 404)
                return
        super().do_GET()

    def _send_html(self, html: Path, status: int) -> None:
        data = inject_reload(html.read_bytes())
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _existing_file(self) -> Path | None:
        path = Path(self.translate_path(self.path.split("?", 1)[0]))
        if path.is_file():
            return path
        if path.is_dir():
            index = path / "index.html"
            return index if index.is_file() else None
        return None

    def _html_file(self) -> Path | None:
        path = self._existing_file()
        if path is not None and path.suffix.lower() in {".html", ".htm"}:
            return path
        return None

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        seen = reload.gen
        try:
            reload.wait_after(seen)
            self.wfile.write(b"data: reload\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return


def serve() -> ThreadingHTTPServer:
    handler = partial(QuietHandler, directory=str(build.DIST))
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> None:
    print("initial build", flush=True)
    build.main()
    serve()
    print(f"serving http://127.0.0.1:{PORT}/  (ctrl-c to stop)", flush=True)
    previous = snapshot(WATCH)
    try:
        while True:
            time.sleep(POLL)
            current = snapshot(WATCH)
            if current == previous:
                continue
            time.sleep(0.2)
            current = snapshot(WATCH)
            changed = {path for path in current.keys() | previous.keys() if current.get(path) != previous.get(path)}
            previous = current
            print("change, rebuilding", flush=True)
            try:
                rebuild(changed)
                reload.bump()
            except Exception as error:
                print(f"rebuild failed: {error}", flush=True)
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
