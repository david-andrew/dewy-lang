"""Parse trees of path-backed modules are reused while the file is unchanged."""
from pathlib import Path

from dewy.reporting import SrcFile
from dewy.semantic import check


def test_unchanged_file_reuses_its_parse_tree(tmp_path: Path) -> None:
    source = tmp_path / "cached.dewy"
    source.write_text("let x = 1\n")
    first, _ = check._parse_module(SrcFile.from_path(source))
    second, _ = check._parse_module(SrcFile.from_path(source))
    assert first.inner[0] is second.inner[0]

    source.write_text("let x = 2\n")
    third, _ = check._parse_module(SrcFile.from_path(source))
    assert third.inner[0] is not first.inner[0]


def test_in_memory_sources_are_not_cached() -> None:
    first, _ = check._parse_module(SrcFile(None, "let x = 1\n"))
    second, _ = check._parse_module(SrcFile(None, "let x = 1\n"))
    assert first.inner[0] is not second.inner[0]


def test_cached_prelude_compiles_identically() -> None:
    from dewy.backend.udewy import codegen

    program = SrcFile(None, 'let main = ():>int64 => { let xs = [1 2 3] printl"{xs.length}" return xs[0] }')
    assert codegen(program) == codegen(program)
