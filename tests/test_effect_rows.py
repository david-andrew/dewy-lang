"""Direct-place rows must agree in check, default and release builds."""
from pathlib import Path
import os
import subprocess
import shutil

import pytest
from tests.support import compiler

FIXTURES = Path(__file__).parent / 'fixtures/effects'


def compile_source(compiler, source, work, mode, env=None):
    args = [compiler, 'check' if mode == 'check' else 'build', source]
    if mode != 'check':
        args += ['-o', work / 'program']
        if mode == 'release':
            args += ['--release']
    return subprocess.run(args, capture_output=True, text=True, timeout=60, env=env)


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('name,output', [('places', '8 8 42\n'), ('callable_forget', '42\n'), ('callable_return', '42\n'), ('ambient', '42\n')])
def test_effect_rows_accept(compiler, tmp_path, mode, name, output):
    result = compile_source(compiler, FIXTURES / f'{name}.dewy', tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode != 'check':
        ran = subprocess.run([tmp_path / 'program'], capture_output=True, text=True, timeout=10)
        assert (ran.returncode, ran.stdout) == (0, output), ran.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('name', ['swapped', 'sibling', 'parent', 'recursive', 'alias_bad',
                                  'unreachable', 'cost', 'default', 'alias_edge', 'recursive_swapped', 'callable_row', 'boxed'])
def test_effect_rows_reject(compiler, tmp_path, mode, name):
    result = compile_source(compiler, FIXTURES / f'{name}.dewy', tmp_path, mode)
    assert result.returncode != 0
    diagnostics = '\n'.join(line.split(': error: ', 1)[1] for line in result.stderr.splitlines()
                            if ': error: ' in line)
    expected = {
        'alias_bad': 'mutable arguments 1 and 2 overlap',
        'callable_recover': 'cannot prove callable effect contract',
        'callable_row': 'cannot prove callable effect contract',
        'callable_indirect': 'cannot prove indirect callable effects',
        'callable_field': 'cannot prove indirect callable effects',
    }.get(name, 'effect contract violation')
    assert expected in diagnostics, result.stdout + result.stderr
    assert 'does not yet support' not in diagnostics


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('name', ['formatter', 'foreign', 'mutation'])
@pytest.mark.parametrize('directory', ['ordinary', 'lib/core'])
def test_effect_rows_implicit_and_path(compiler, tmp_path, mode, name, directory):
    location = tmp_path / directory
    env = None
    if directory == 'lib/core':
        # Make the helper genuinely part of the configured library root. A
        # merely misleading directory name would not exercise pos_in_lib.
        library = subprocess.run([compiler, '--print-lib'], capture_output=True,
                                 text=True, check=True).stdout.strip()
        shutil.copytree(library, tmp_path / 'lib')
        env = dict(os.environ, DEWY_CORE_LIB=str(tmp_path / 'lib'))
    location.mkdir(parents=True, exist_ok=True)
    helper = location / 'helper.jo'
    helper.write_text((FIXTURES / f'{name}.jo').read_text())
    source = tmp_path / 'main.dewy'
    source.write_text(f'from p"{directory}/helper.jo" import (hidden)\n'
                      'bad=():>int64 & no_effects=>hidden()\nmain=():>void=>exit(0)\n')
    result = compile_source(compiler, source, tmp_path, mode, env)
    assert result.returncode != 0
    assert 'effect contract violation' in result.stderr, result.stdout + result.stderr


@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('body,accepted', [('42', True), ('[42][0]', False)])
def test_effect_rows_internal_policy(compiler, tmp_path, mode, body, accepted):
    source = tmp_path / 'main.dewy'
    source.write_text(f'probe=():>int64=>{body}\nmain=():>void=>{{let value=probe()}}\n')
    env = dict(os.environ, DEWY_INTERNAL_EFFECT_POLICY='scalar-no-effects')
    result = compile_source(compiler, source, tmp_path, mode, env)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if not accepted:
        assert 'effect contract violation' in result.stderr


@pytest.mark.core_quick
def test_effect_rows_check_without_lowering(compiler, tmp_path):
    env = dict(os.environ, SLOPPY_STOP='check')
    result = compile_source(compiler, FIXTURES / 'unreachable.dewy', tmp_path, 'check', env)
    assert result.returncode != 0
    assert 'effect contract violation' in result.stderr, result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('mode', ['check', 'default', 'release'])
@pytest.mark.parametrize('name', ['callable_indirect', 'callable_field', 'lambda', 'callable_recover'])
def test_contracted_indirect_calls(compiler, tmp_path, mode, name):
    result = compile_source(compiler, FIXTURES / f'{name}.dewy', tmp_path, mode)
    assert result.returncode == 0, result.stdout + result.stderr
    if mode != 'check':
        ran = subprocess.run([tmp_path / 'program'], timeout=10)
        assert ran.returncode == (0 if name in ('lambda', 'callable_recover') else 2)
