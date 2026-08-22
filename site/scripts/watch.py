"""Rebuild the site when sources change, and keep serving ``site/dist``."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build
from udewy_showcase import DEMOS, demo_for_path

DEFAULT_PORT = 9000
POLL = 0.4
SKIP_DIRS = {".git", "__pycache__", "book", "dist", "designs"}
WATCH = [
    build.STATIC,
    build.LEARN,
    build.REFERENCE,
    build.UDEWY_REFERENCE / "book.toml",
    build.UDEWY_REFERENCE / "theme",
    build.UDEWY_README,
    *build.PLAYGROUND_PAGE_INPUTS,
    build.INSTALL_SCRIPT,
    *[demo.watch for demo in DEMOS],
]
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
    build.build_udewy_spec(mdbook)
    build.highlight_tree(build.DIST / "udewy")
    demo_slugs = {
        demo.slug
        for path in changed
        if (demo := demo_for_path(path)) is not None
    }
    if demo_slugs:
        build.require_tool("wat2wasm")
        build.compile_showcase_demos(demo_slugs)
    playground_inputs = {path.resolve() for path in build.PLAYGROUND_PAGE_INPUTS}
    if playground_inputs & {path.resolve() for path in changed}:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "port",
        nargs="?",
        type=int,
        default=DEFAULT_PORT,
        help=f"port to serve on (default: {DEFAULT_PORT})",
    )
    return parser.parse_args()


def _cmdline(pid: int) -> bytes:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return b""


def _pid_file(port: int) -> Path:
    return Path(f"/tmp/dewy-watch-{port}.pid")


def _listen_inode(port: int) -> str | None:
    wanted = f"{port:04X}"
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            rows = table.read_text().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            cols = row.split()
            if cols[3] == "0A" and cols[1].rsplit(":", 1)[-1].upper() == wanted:
                return cols[9]
    return None


def _listening_watch_pid(port: int) -> int | None:
    inode = _listen_inode(port)
    if inode is None:
        return None
    needle = f"socket:[{inode}]"
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            fds = proc.joinpath("fd").iterdir()
        except OSError:
            continue
        for fd in fds:
            try:
                if os.readlink(fd) == needle and b"watch.py" in _cmdline(int(proc.name)):
                    return int(proc.name)
            except OSError:
                continue
    return None


def _recorded_watch_pid(port: int) -> int | None:
    try:
        pid = int(_pid_file(port).read_text().strip())
    except (OSError, ValueError):
        return None
    if pid != os.getpid() and b"watch.py" in _cmdline(pid):
        return pid
    return None


def reclaim_port(port: int) -> None:
    pid = _recorded_watch_pid(port) or _listening_watch_pid(port)
    if pid is None:
        return
    print(f"replacing watch.py on port {port} (pid {pid})", flush=True)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(0.25)


def serve(port: int) -> ThreadingHTTPServer:
    reclaim_port(port)
    handler = partial(QuietHandler, directory=str(build.DIST))
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as error:
        raise SystemExit(f"could not bind 127.0.0.1:{port}: {error}") from error
    _pid_file(port).write_text(f"{os.getpid()}\n")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> None:
    args = parse_args()
    print("initial build", flush=True)
    build.main()
    serve(args.port)
    print(f"serving http://127.0.0.1:{args.port}/  (ctrl-c to stop)", flush=True)
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
