"""Dynamic strings keep their results without retaining validation scratch."""
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('fixture_name', ['native_string_scratch', 'native_string_materialization'])
@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_string_scratch(tmp_path, target, fixture_name):
    fixture = Path(__file__).resolve().parents[1] / f'fixtures/{fixture_name}.dewy'
    output = tmp_path / 'string-scratch.udewy'
    output.write_text(codegen(SrcFile.from_path(fixture), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
