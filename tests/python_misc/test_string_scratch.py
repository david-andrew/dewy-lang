"""Dynamic strings keep their results without retaining validation scratch."""
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('fixture_name', ['native_string_scratch', 'native_string_materialization', 'native_string_lifetimes'])
@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_string_scratch(tmp_path, target, fixture_name):
    fixture = Path(__file__).resolve().parents[1] / f'fixtures/{fixture_name}.dewy'
    source = fixture
    if fixture_name == 'native_string_lifetimes':
        # The hosted backend uses regions for escaping string results. Check
        # the shared value semantics here; the native driver separately runs
        # this fixture's stricter reference-counted retention budget.
        source = tmp_path / 'string-values.dewy'
        source.write_text(fixture.read_text().replace('let main=', 'let retention_check=')
                          + '\nlet main=():>int64=>if repeated() 42 else 1\n')
    output = tmp_path / 'string-scratch.udewy'
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
