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


def test_disk_parse_cache_restores_source_spans_without_reparsing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / 'span-cache.dewy'
    source.write_text('let value = 42\n')
    first, _ = check._parse_module(SrcFile.from_path(source))
    monkeypatch.setattr(check, '_parsed_modules', {})

    def unexpected_parse(*args, **kwargs):
        raise AssertionError('an unchanged disk cache should restore the parsed syntax')

    monkeypatch.setattr(check.p0, 'parse', unexpected_parse)
    second, _ = check._parse_module(SrcFile.from_path(source))
    assert second.inner[0] is not first.inner[0]
    assert second.inner[0].loc == first.inner[0].loc
