"""Focused pinned-core regressions for changes to shared checking and lowering."""
import os
import subprocess
from pathlib import Path

import pytest

CASES = ('recursive_values', 'recursive_list', 'recursive_tree', 'recursive_expr', 'held_views', 'held_views_copies',
         'regex', 'arrays', 'cow', 'bounds', 'loops', 'loopdecl', 'loopopt', 'optloops',
         'loop_combined_mut', 'loop_kv_mut', 'arg_alias_copy', 'loop_and_unpack',
         'optionals', 'unions', 'narrow_none', 'union_infer', 'match', 'match_path', 'enum_union')


@pytest.mark.parametrize('name', CASES)
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_pinned_core_behavior(tmp_path, name, release):
    compiler = os.environ.get('DEWY_CORE_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CORE_COMPILER for core regression checks')
    compiler = Path(compiler).resolve(strict=True)
    fixtures = Path(__file__).resolve().parents[1] / 'tests/fixtures/upstream'
    source = tmp_path / f'{name}.jo'
    source.write_bytes((fixtures / f'{name}.jo').read_bytes())
    expected = (fixtures / f'{name}.expected').read_text()
    binary = tmp_path / name
    flags = ['--release'] if release else []
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(compiler.parent.parent / 'lib'), DEWY_EMIT_WORKERS='1')
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags], env=env,
                           capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    result = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == expected
