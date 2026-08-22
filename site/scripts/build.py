"""Build the complete Dewy website into ``site/dist``."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from highlight_udewy import highlight_tree
from udewy_showcase import DEMOS
from udewy_spec_book import generate as generate_udewy_spec

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
DIST = SITE_ROOT / "dist"
STATIC = SITE_ROOT / "static"
LEARN = SITE_ROOT / "learn"
REFERENCE = SITE_ROOT / "reference"
UDEWY_REFERENCE = SITE_ROOT / "udewy" / "reference"
UDEWY_README = REPO_ROOT / "udewy" / "README.md"
PLAYGROUND_SOURCE = REPO_ROOT / "udewy" / "tests" / "web" / "playground.udewy"
PLAYGROUND_WEB = REPO_ROOT / "udewy" / "third_party" / "web"
PLAYGROUND_PAGE_INPUTS = (
    PLAYGROUND_SOURCE,
    PLAYGROUND_WEB / "dom.udewy",
    PLAYGROUND_WEB / "highlight.udewy",
    PLAYGROUND_WEB / "playground_host.js",
)
BOOTSTRAP = REPO_ROOT / "udewy" / "bootstrap"
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
UDEWY_INSTALL_SCRIPT = REPO_ROOT / "udewy" / "install.sh"
CACHE = REPO_ROOT / "__dewycache__"
SHOWCASE_HASHES = CACHE / "showcase-hashes.json"


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
    udewy_dest = DIST / "udewy"
    udewy_dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(UDEWY_INSTALL_SCRIPT, udewy_dest / "install.sh")


def build_book(source: Path, destination: Path, mdbook: str) -> None:
    run([mdbook, "build", str(source), "--dest-dir", str(destination)])


def build_udewy_spec(mdbook: str) -> None:
    generate_udewy_spec()
    build_book(UDEWY_REFERENCE, DIST / "udewy" / "reference", mdbook)


def _paths_digest(paths: list[Path] | tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for root in paths:
        root = root.resolve()
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in files:
            digest.update(path.relative_to(REPO_ROOT).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _load_showcase_hashes() -> dict[str, str]:
    try:
        data = json.loads(SHOWCASE_HASHES.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(slug): str(digest) for slug, digest in data.items()}


def _save_showcase_hashes(hashes: dict[str, str]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    SHOWCASE_HASHES.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")


def compile_showcase_demos(slugs: set[str] | None = None) -> None:
    dest_root = DIST / "udewy" / "showcase" / "demos"
    dest_root.mkdir(parents=True, exist_ok=True)
    hashes = _load_showcase_hashes()
    for demo in DEMOS:
        if slugs is not None and demo.slug not in slugs:
            continue
        generated = CACHE / f"{demo.source.stem}.html"
        destination = dest_root / demo.slug
        destination.mkdir(parents=True, exist_ok=True)
        digest = demo.source_digest()
        if hashes.get(demo.slug) == digest and generated.is_file():
            print(f"showcase {demo.slug}: unchanged, reusing cache", flush=True)
            shutil.copy2(generated, destination / "index.html")
            continue
        run(
            [
                sys.executable,
                "-m",
                "udewy",
                "-c",
                "--target",
                "wasm32",
                str(demo.source),
            ]
        )
        if not generated.is_file():
            raise SystemExit(f"µDewy did not produce the expected file: {generated}")
        shutil.copy2(generated, destination / "index.html")
        hashes[demo.slug] = digest
        _save_showcase_hashes(hashes)


def build_playground() -> None:
    generated = CACHE / "playground.html"
    destination = DIST / "playground"
    destination.mkdir(parents=True, exist_ok=True)
    hashes = _load_showcase_hashes()
    bootstrap_digest = _paths_digest((BOOTSTRAP,))
    playground_digest = _paths_digest((*PLAYGROUND_PAGE_INPUTS, BOOTSTRAP))
    if hashes.get("playground") == playground_digest and generated.is_file():
        print("playground: unchanged, reusing cache", flush=True)
        shutil.copy2(generated, destination / "index.html")
        return

    wasm = PLAYGROUND_WEB / "artifacts" / "web_compiler.wasm"
    wabt = PLAYGROUND_WEB / "artifacts" / "wabt.js"
    if hashes.get("web_compiler") == bootstrap_digest and wasm.is_file() and wabt.is_file():
        print("web compiler: unchanged, reusing cache", flush=True)
    else:
        run([sys.executable, "udewy/third_party/web/setup_web_compiler.py"])
        hashes["web_compiler"] = bootstrap_digest
        _save_showcase_hashes(hashes)

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
    if not generated.is_file():
        raise SystemExit(f"µDewy did not produce the expected file: {generated}")
    shutil.copy2(generated, destination / "index.html")
    hashes["playground"] = playground_digest
    _save_showcase_hashes(hashes)


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
        "udewy/",
        "udewy/showcase/",
        "udewy/reference/",
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
    build_udewy_spec(mdbook)
    highlight_tree(DIST / "udewy")
    compile_showcase_demos()
    build_playground()
    write_sitemap()
    run([sys.executable, "site/scripts/check_links.py", str(DIST)])
    print(f"Built site: {DIST}")


if __name__ == "__main__":
    main()
