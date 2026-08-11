from pathlib import Path
from shutil import which

import pytest

from src.cleanparse.reporting import SrcFile
from src.cleanparse.backend.udewy import codegen
from udewy.frontend import entry_point

here = Path(__file__).parent
fixtures = here.parent.parent / 'src' / 'cleanparse' / 'tests'


def x86_64_toolchain_available() -> bool:
    return which('as') is not None and which('ld') is not None


def test_minimal2_golden_source() -> None:
    srcfile = SrcFile.from_path(fixtures / 'minimal2.dewy')
    emitted = codegen(srcfile)
    golden = (fixtures / 'minimal2.udewy').read_text()
    assert emitted == golden


@pytest.mark.skipif(not x86_64_toolchain_available(), reason='as/ld not available')
def test_minimal2_compiles_and_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    srcfile = SrcFile.from_path(fixtures / 'minimal2.dewy')
    emitted = codegen(srcfile)

    udewy_path = tmp_path / 'minimal2.udewy'
    udewy_path.write_text(emitted)

    # entry_point writes __dewycache__ relative to cwd; keep artifacts in tmp_path
    monkeypatch.chdir(tmp_path)
    exit_code = entry_point(udewy_path, [])
    assert exit_code == 42
