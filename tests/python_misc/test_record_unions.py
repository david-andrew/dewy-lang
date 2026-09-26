"""Record unions keep one owner per block across every representation boundary.

Native lowering stores a union of one root's records as that root's handle
(zero for `none`); hosted lowering keeps tagged cells. Either way the fixture's
second pass must leave the live arena bytes unchanged.
"""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_record_unions_run_without_leaking(tmp_path, target):
    source = tmp_path / 'record-unions.dewy'
    source.write_text((ROOT / 'tests/fixtures/native_record_unions.dewy').read_text())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_argument_temporaries_run_without_leaking(tmp_path, target):
    source = tmp_path / 'argument-temporaries.dewy'
    source.write_text((ROOT / 'tests/fixtures/native_argument_temporaries.dewy').read_text())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_runtime_range_ends_run(tmp_path, target):
    source = tmp_path / 'range-ends.dewy'
    source.write_text((ROOT / 'tests/fixtures/native_runtime_range_ends.dewy').read_text())
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30)
    assert result.returncode == 42, result.stdout + result.stderr
