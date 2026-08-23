from pathlib import Path
from shutil import which

import pytest

from udewy.cache import (
    EXTERNAL_DIR_NAME,
    cache_artifact,
    cache_layout,
    cache_source_rel,
    path_hash12,
)
from udewy.frontend import entry_point


def _x86_64_toolchain_available() -> bool:
    return which("as") is not None and which("ld") is not None


def test_relative_source_is_mirrored(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = Path("examples") / "hello.udewy"
    src.parent.mkdir()
    src.write_text("")

    assert cache_source_rel(src, cwd=tmp_path) == Path("examples/hello.udewy")
    assert cache_layout(src, cwd=tmp_path) == (Path("__dewycache__/examples"), "hello")
    assert cache_artifact(src, ".udewy", cwd=tmp_path) == Path("__dewycache__/examples/hello.udewy")
    assert cache_artifact(src, cwd=tmp_path) == Path("__dewycache__/examples/hello")


def test_cache_prefix_is_stripped_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = Path("__dewycache__") / "examples" / "hello.udewy"
    src.parent.mkdir(parents=True)
    src.write_text("")

    assert cache_source_rel(src, cwd=tmp_path) == Path("examples/hello.udewy")
    assert cache_artifact(src, cwd=tmp_path) == Path("__dewycache__/examples/hello")


def test_same_stem_different_dirs_do_not_collide(tmp_path: Path) -> None:
    a = tmp_path / "a" / "main.udewy"
    b = tmp_path / "b" / "main.udewy"
    assert cache_artifact(a, cwd=tmp_path) != cache_artifact(b, cwd=tmp_path)
    assert cache_artifact(a, cwd=tmp_path) == Path("__dewycache__/a/main")
    assert cache_artifact(b, cwd=tmp_path) == Path("__dewycache__/b/main")


def test_path_outside_cwd_uses_external_hash(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere" / "nested" / "prog.udewy"
    cwd = tmp_path / "work"
    cwd.mkdir()
    other.parent.mkdir(parents=True)
    other.write_text("")

    digest = path_hash12(other)
    rel = cache_source_rel(other, cwd=cwd)
    assert rel == Path(EXTERNAL_DIR_NAME) / digest / "elsewhere" / "nested" / "prog.udewy"
    assert cache_artifact(other, cwd=cwd) == (
        Path("__dewycache__") / EXTERNAL_DIR_NAME / digest / "elsewhere" / "nested" / "prog"
    )


def test_cousin_folders_do_not_collide(tmp_path: Path) -> None:
    cwd = tmp_path / "a" / "b" / "c"
    left = tmp_path / "a" / "d" / "foo" / "main.udewy"
    right = tmp_path / "a" / "e" / "foo" / "main.udewy"
    cwd.mkdir(parents=True)

    left_art = cache_artifact(left, cwd=cwd)
    right_art = cache_artifact(right, cwd=cwd)
    assert left_art != right_art
    assert left_art.parts[:2] == ("__dewycache__", EXTERNAL_DIR_NAME)
    assert left_art.parts[2] == path_hash12(left)
    assert len(left_art.parts[2]) == 12
    assert Path(*left_art.parts[3:]) == Path("d/foo/main")
    assert Path(*right_art.parts[3:]) == Path("e/foo/main")


def test_cwd_root_source_stays_flat(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = Path("smoke.udewy")
    src.write_text("")

    assert cache_layout(src, cwd=tmp_path) == (Path("__dewycache__"), "smoke")
    assert cache_artifact(src, cwd=tmp_path) == Path("__dewycache__/smoke")


@pytest.mark.skipif(not _x86_64_toolchain_available(), reason="as/ld not available")
def test_nested_source_writes_mirrored_binary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = Path("nested") / "hello.udewy"
    src.parent.mkdir()
    src.write_text("let main = ():>int => {\n    return 7\n}\n")

    assert entry_point(src, []) == 7
    assert (tmp_path / "__dewycache__" / "nested" / "hello").is_file()
    assert not (tmp_path / "__dewycache__" / "hello").exists()


@pytest.mark.skipif(not _x86_64_toolchain_available(), reason="as/ld not available")
def test_cached_intermediate_does_not_double_nest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    src = Path("__dewycache__") / "examples" / "hello.udewy"
    src.parent.mkdir(parents=True)
    src.write_text("let main = ():>int => {\n    return 3\n}\n")

    assert entry_point(src, []) == 3
    assert (tmp_path / "__dewycache__" / "examples" / "hello").is_file()
    assert not (tmp_path / "__dewycache__" / "__dewycache__").exists()


@pytest.mark.skipif(not _x86_64_toolchain_available(), reason="as/ld not available")
def test_outside_cwd_compile_writes_external_tree(tmp_path: Path, monkeypatch) -> None:
    cwd = tmp_path / "work"
    src = tmp_path / "cousin" / "hello.udewy"
    cwd.mkdir()
    src.parent.mkdir()
    src.write_text("let main = ():>int => {\n    return 5\n}\n")
    monkeypatch.chdir(cwd)

    assert entry_point(src, []) == 5
    artifact = cwd / cache_artifact(src, cwd=cwd)
    assert artifact.is_file()
    assert (cwd / "__dewycache__" / EXTERNAL_DIR_NAME).is_dir()
    assert not (cwd / "__dewycache__" / "hello").exists()
