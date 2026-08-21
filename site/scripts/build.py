"""Build the complete Dewy website into ``site/dist``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
DIST = SITE_ROOT / "dist"
STATIC = SITE_ROOT / "static"
LEARN = SITE_ROOT / "learn"
REFERENCE = SITE_ROOT / "reference"
PLAYGROUND_SOURCE = REPO_ROOT / "udewy" / "tests" / "web" / "playground.udewy"
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
CACHE = REPO_ROOT / "__dewycache__"


def run(command: list[str], *, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(command)
    print(f"+ {printable}", flush=True)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(command, cwd=cwd, env=env, check=True)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise SystemExit(
            f"Required tool {name!r} was not found on PATH. "
            f"See site/README.md for local setup."
        )
    return path


def copy_static_site() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(STATIC, DIST, ignore=shutil.ignore_patterns("designs"))
    (DIST / ".nojekyll").write_text("")
    copy_install_script()


def copy_install_script() -> None:
    shutil.copy2(INSTALL_SCRIPT, DIST / "install.sh")


def build_book(source: Path, destination: Path, mdbook: str) -> None:
    run([mdbook, "build", str(source), "--dest-dir", str(destination)])


def build_playground() -> None:
    run([sys.executable, "udewy/third_party/web/setup_web_compiler.py"])
    run(
        [
            sys.executable,
            "-m",
            "udewy",
            "-c",
            "--target",
            "wasm32",
            str(PLAYGROUND_SOURCE),
        ]
    )
    generated = CACHE / "playground.html"
    if not generated.is_file():
        raise SystemExit(f"µDewy did not produce the expected file: {generated}")
    destination = DIST / "playground"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated, destination / "index.html")


def write_sitemap() -> None:
    base = "https://dewy-lang.org"
    routes = [
        "",
        "learn/",
        "reference/",
        "examples/",
        "playground/",
        "install/",
        "status/",
        "tools/",
        "contribute/",
    ]
    urls = "\n".join(f"  <url><loc>{base}/{route}</loc></url>" for route in routes)
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def main() -> None:
    mdbook = require_tool("mdbook")
    require_tool("wat2wasm")
    copy_static_site()
    build_book(LEARN, DIST / "learn", mdbook)
    build_book(REFERENCE, DIST / "reference", mdbook)
    build_playground()
    write_sitemap()
    run([sys.executable, "site/scripts/check_links.py", str(DIST)])
    print(f"Built site: {DIST}")


if __name__ == "__main__":
    main()
