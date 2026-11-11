"""A toolchain version in hex or with separators compares as the frozen Jo's `to_int` reads it."""
from tests.selfhost_facts_double import compare_moved
from tests.support import compiler  # noqa: F401


def test_directive_ops_version_text_twins(compiler, tmp_path, monkeypatch):
    # Jo reads `0x2` as 2, so a module for 0.1.0 is not newer than toolchain 0x2.0.0.
    (tmp_path / 'versioned.dewy').write_text("$dewy.version = '0.1.0'\n\nprintl($dewy.version)\n")
    monkeypatch.setenv('DEWY_TOOLCHAIN_VERSION', '0x2.0.0')
    assert compare_moved(compiler, tmp_path, monkeypatch, [str(tmp_path / 'versioned')]) == 1
