"""An array field's current length never replaces its declared store type."""
import subprocess

import test_bootstrap_prelude as prelude
from dewy.reporting import SrcFile
from dewy.semantic import check

CASES = [
    'Box:type=[values:array<int64>]\nlet box=Box[[1]]\nbox.values.clear\nbox.values.push(42)',
    'Box:type=[values:array<int64> reset=()=>{values.clear values.push(42)}]\nlet box=Box[[1]]\nbox.reset',
    'Box:type=[values:array<int64> reset=()=>{values.clear let replacement:array<int64>=[42] loop value in replacement {values.push(value)}}]\nlet box=Box[[1]]\nbox.reset',
]


def test_native_array_field_store_contract(tmp_path):
    binary = prelude.module_driver(tmp_path)
    for index, text in enumerate(CASES):
        source = tmp_path / f'array-field-{index}.dewy'
        source.write_text(text)
        check.typecheck_and_resolve(SrcFile.from_path(source))
        result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
    source = tmp_path / 'fixed-field.dewy'
    source.write_text('Box:type=[values:array<int64 length=1>]\nlet box=Box[[1]]\nbox.values.clear')
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode != 0
    assert 'exact-length arrays cannot change length' in result.stderr
