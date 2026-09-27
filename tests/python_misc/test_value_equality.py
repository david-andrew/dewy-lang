"""`=?` compares arrays and records by value: element-wise and field-wise."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('fixture', ['value_equality', 'value_equality_evaluation'])
@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_value_equality(tmp_path, target, fixture):
    source = tmp_path / 'value-equality.dewy'
    source.write_text((ROOT / f'tests/fixtures/{fixture}.dewy').read_text())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('element,value', [('dict<string int64>', "['x' -> 1]"), ('set<int64>', 'set[1]')])
@pytest.mark.parametrize('container', ['record', 'array'])
def test_nested_container_equality_is_pending(element, value, container):
    from dewy.reporting import ReportException
    source = (f'Box:type=[items:{element}]\nmain=():>int64=>if Box[{value}] =? Box[{value}] 42 else 1'
              if container == 'record' else
              f'main=():>int64=>{{let a:array<{element}>=[{value}] let b:array<{element}>=[{value}] return if a =? b 42 else 1}}')
    with pytest.raises(ReportException, match='value equality of a dictionary or set'):
        codegen(SrcFile(None, source))


def test_native_value_equality_evaluation(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    source = (ROOT / 'tests/fixtures/value_equality_evaluation.dewy').read_text()
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=[source], errors=[])
