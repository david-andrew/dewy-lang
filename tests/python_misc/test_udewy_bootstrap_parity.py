"""Drift detection between the Python compiler (udewy/backend/*) and the
bootstrap compiler (udewy/bootstrap/backend/*).

The host JS / HTML templates in wasm.py and wasm.udewy, and the C helpers /
wrappers / preludes in c.py and c.udewy, are duplicated by hand. These tests
compile a tiny program with both compilers and compare the output to catch
drift.
"""

from __future__ import annotations

from os import environ
from pathlib import Path
from shutil import which
import subprocess
from tempfile import TemporaryDirectory

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BOOTSTRAP_MAIN = REPO_ROOT / "udewy" / "bootstrap" / "main.udewy"


# Program is irrelevant for the wasm host-JS / HTML check (those blobs are
# emitted unconditionally) but exercises core C helpers so the C parity test
# fails if helper bodies diverge in behaviour.
SMOKE_SRC = """
let main = ():>int => {
    let tmp:int = __alloca__(16)
    __store__(0x1122334455667788 tmp)
    if __load__(tmp) not=? 0x1122334455667788 {
        return 1
    }
    __store_u32__(0xDEADBEEF tmp)
    if __load_u32__(tmp) not=? 0xDEADBEEF {
        return 2
    }
    __store_u16__(0xCAFE tmp)
    if __load_u16__(tmp) not=? 0xCAFE {
        return 3
    }
    __store_u8__(0x42 tmp)
    if __load_u8__(tmp) not=? 0x42 {
        return 4
    }
    if __signed_shr__(0xFFFF_FFFF_FFFF_FFF0 2) not=? 0xFFFF_FFFF_FFFF_FFFC {
        return 5
    }
    return 0
}
"""


@pytest.fixture(scope="session")
def bootstrap_binary(tmp_path_factory) -> Path:
    """Build the bootstrap compiler with Python's compiler once per session."""
    out_dir = tmp_path_factory.mktemp("bootstrap")
    env = {**environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        ["python", "-m", "udewy", "-c", str(BOOTSTRAP_MAIN)],
        cwd=out_dir, check=True, env=env,
    )
    binary = out_dir / "__dewycache__" / "main"
    assert binary.exists()
    return binary


def _compile_with(compiler_cmd: list[str], src: str, target: str, work: Path) -> Path:
    """Compile `src` with the given compiler. Returns the produced artifact."""
    src_path = work / "smoke.udewy"
    src_path.write_text(src)
    env = {**environ, "PYTHONPATH": str(REPO_ROOT)}
    subprocess.run(
        compiler_cmd + ["-c", "--target", target, str(src_path)],
        cwd=work, check=True, env=env,
    )
    cache_dir = work / "__dewycache__"
    if target == "wasm32":
        return cache_dir / "smoke.html"
    return cache_dir / "smoke"


def _html_diff_excluding_b64(py_html: str, bs_html: str) -> list[tuple[str, str]]:
    """Return all line-level differences except the embedded base64 blob.

    The base64 line legitimately differs because Python and bootstrap emit
    slightly different WAT (different label allocation, formatting), so the
    compressed bytes don't byte-match. Everything else (host JS, server
    lifecycle JS, HTML scaffolding) must.
    """
    diffs: list[tuple[str, str]] = []
    py_lines = py_html.splitlines()
    bs_lines = bs_html.splitlines()
    assert len(py_lines) == len(bs_lines), (
        f"line count differs: py={len(py_lines)} bs={len(bs_lines)}"
    )
    for py, bs in zip(py_lines, bs_lines):
        if py == bs:
            continue
        if 'application/wasm-b64' in py or 'application/wasm-b64' in bs:
            # The base64 follows on the next line, which is just the blob.
            continue
        # The line right after the wasm-data script open tag is the b64 payload.
        # Heuristic: if both lines look like base64 (no spaces, mostly A-Za-z0-9+/=)
        # treat as expected divergence.
        if _looks_like_b64(py) and _looks_like_b64(bs):
            continue
        diffs.append((py, bs))
    return diffs


def _looks_like_b64(line: str) -> bool:
    if len(line) < 100:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    return all(c in allowed for c in line)


def test_wasm_host_blobs_match_between_compilers(bootstrap_binary, tmp_path) -> None:
    """Catches drift in JS / HTML strings duplicated across wasm.py and wasm.udewy."""
    if which("wat2wasm") is None:
        pytest.skip("wat2wasm not installed")

    py_work = tmp_path / "py"
    py_work.mkdir()
    py_html = _compile_with(["python", "-m", "udewy"], SMOKE_SRC, "wasm32", py_work).read_text()

    bs_work = tmp_path / "bs"
    bs_work.mkdir()
    bs_html = _compile_with([str(bootstrap_binary)], SMOKE_SRC, "wasm32", bs_work).read_text()

    diffs = _html_diff_excluding_b64(py_html, bs_html)
    if diffs:
        sample = "\n".join(f"  py: {p!r}\n  bs: {b!r}" for p, b in diffs[:10])
        pytest.fail(
            f"{len(diffs)} non-b64 line(s) differ between Python and bootstrap WASM HTML.\n"
            f"This usually means the host JS / HTML template embeds in wasm.py and\n"
            f"udewy/bootstrap/backend/wasm.udewy have drifted. First 10:\n{sample}"
        )


def test_c_helpers_behaviour_matches_between_compilers(bootstrap_binary, tmp_path) -> None:
    """Catches drift in C helpers/wrappers/preludes duplicated across c.py and c.udewy.

    Both compilers must produce an executable that returns the same exit code
    for a program that exercises load/store helpers, alloca, and signed shift.
    """
    if which("cc") is None:
        pytest.skip("cc not installed")

    py_work = tmp_path / "py"
    py_work.mkdir()
    py_bin = _compile_with(["python", "-m", "udewy"], SMOKE_SRC, "c", py_work)
    py_exit = subprocess.run([str(py_bin)]).returncode

    bs_work = tmp_path / "bs"
    bs_work.mkdir()
    bs_bin = _compile_with([str(bootstrap_binary)], SMOKE_SRC, "c", bs_work)
    bs_exit = subprocess.run([str(bs_bin)]).returncode

    assert py_exit == 0, f"Python compiler produced a binary that exits {py_exit}"
    assert bs_exit == 0, f"Bootstrap compiler produced a binary that exits {bs_exit}"
    assert py_exit == bs_exit
