"""Catalog of µDewy wasm demos bundled into the website showcase."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GITHUB = "https://github.com/david-andrew/dewy-lang"


@dataclass(frozen=True)
class Demo:
    slug: str
    title: str
    source: Path
    watch: Path
    github_path: str
    blurb: str

    @property
    def github_url(self) -> str:
        kind = "tree" if (REPO_ROOT / self.github_path).is_dir() else "blob"
        return f"{GITHUB}/{kind}/master/{self.github_path}"

    def source_digest(self) -> str:
        digest = hashlib.sha256()
        watch = self.watch
        if watch.is_file():
            digest.update(watch.read_bytes())
            return digest.hexdigest()
        for path in sorted(p for p in watch.rglob("*") if p.is_file()):
            digest.update(path.relative_to(watch).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()


DEMOS: tuple[Demo, ...] = (
    Demo(
        slug="plasma",
        title="Plasma",
        source=REPO_ROOT / "udewy/tests/test_webgl_plasma.udewy",
        watch=REPO_ROOT / "udewy/tests/test_webgl_plasma.udewy",
        github_path="udewy/tests/test_webgl_plasma.udewy",
        blurb="A fullscreen WebGL fragment shader driven from µDewy.",
    ),
    Demo(
        slug="water",
        title="Water",
        source=REPO_ROOT / "udewy/tests/test_webgl_water.udewy",
        watch=REPO_ROOT / "udewy/tests/test_webgl_water.udewy",
        github_path="udewy/tests/test_webgl_water.udewy",
        blurb="Pointer motion and clicks spawn overlapping ripple rings.",
    ),
    Demo(
        slug="slime-volleyball",
        title="Slime Volleyball",
        source=REPO_ROOT / "udewy/tests/test_slime_volleyball.udewy",
        watch=REPO_ROOT / "udewy/tests/test_slime_volleyball.udewy",
        github_path="udewy/tests/test_slime_volleyball.udewy",
        blurb="A two-slime match with CPU, stages, and short sound effects.",
    ),
    Demo(
        slug="crypt",
        title="μCrypt",
        source=REPO_ROOT / "udewy/tests/crypt/crypt.udewy",
        watch=REPO_ROOT / "udewy/tests/crypt",
        github_path="udewy/tests/crypt",
        blurb="A Wolfenstein-style raycast dungeon with combat and procedural audio.",
    ),
    Demo(
        slug="uzero2",
        title="μZero2",
        source=REPO_ROOT / "udewy/tests/uzero2/uzero2.udewy",
        watch=REPO_ROOT / "udewy/tests/uzero2",
        github_path="udewy/tests/uzero2",
        blurb="A hover racer with tracks, AI, an editor, and an engine note.",
    ),
)


def demo_for_path(path: Path) -> Demo | None:
    path = path.resolve()
    for demo in DEMOS:
        watch = demo.watch.resolve()
        if path == watch or watch in path.parents:
            return demo
    return None
