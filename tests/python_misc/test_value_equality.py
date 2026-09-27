"""`=?` compares arrays and records by value: element-wise and field-wise."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_value_equality(tmp_path, target):
    source = tmp_path / 'value-equality.dewy'
    source.write_text((ROOT / 'tests/fixtures/value_equality.dewy').read_text())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 42, result.stdout + result.stderr
