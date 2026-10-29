"""Checked evaluator: frozen whole-compiler outputs and private instruction ordinals."""
from pathlib import Path
import os
import re
import shutil
import subprocess

import pytest
from tests.support import ROOT, compiler  # noqa: F401


def enum_members(text, name):
    match = re.search(r'^enum '+name+r':([^\n]*)(\n(?:[ \t]+[^\n]*\n)*)?', text, re.M)
    assert match, name
    return re.findall(r'[A-Za-z_]\w*', re.sub(r'#[^\n]*', '', match[1] + (match[2] or '')))


def test_checked_eval_instruction_ordinals():
    owner = (ROOT / 'compiler/checked_eval.dewy').read_text()
    for original, private, table, source in [
        ('IN', 'CXIN', 'intrinsic_kind', 'expr'),
        ('CV', 'CXCV', 'conversion', 'expr'),
        ('Tok', 'Tok', 'token', 'checker_tokens'),
    ]:
        expected = enum_members((ROOT / f'compiler/{source}.jo').read_text(), original)
        entries = re.search(r'^let cx_'+table+r'_values:[^=]*=\[([^\n]*)\]', owner, re.M)
        assert entries
        assert re.findall(private+r'\.(\w+)', entries[1]) == expected


@pytest.fixture(scope='module')
def frozen_evaluator(compiler, tmp_path_factory):  # noqa: F811
    directory = tmp_path_factory.mktemp('checked-eval-frozen')
    sources = directory / 'compiler'
    shutil.copytree(ROOT / 'compiler', sources)
    for name in ('comptime.jo', 'math_comptime.jo'):
        path = sources / name
        path.write_text(path.read_text().replace("use 'checked_eval.dewy'", "use 'checked_eval.jo'"))
    binary = directory / 'dewy-core'
    built = subprocess.run([compiler, 'build', sources / 'main.jo', '-o', binary],
                           env={**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'},
                           capture_output=True, text=True, timeout=180)
    assert built.returncode == 0, built.stdout + built.stderr
    return binary


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checked_eval_twins(compiler, frozen_evaluator, tmp_path, release):  # noqa: F811
    sources = [ROOT / f'tests/cases/comptime/{name}.dewy' for name in
               ('arrays', 'functions', 'control', 'storage', 'semantics', 'interpolation',
                'reflection', 'divide_zero', 'host_effect', 'overflow', 'selfhost_growth')]
    env = {**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}
    for source in sources:
        results = []
        for binary in (compiler, frozen_evaluator):
            output = tmp_path / 'program'
            built = subprocess.run([binary, 'build', source, '-o', output,
                                    *(['--release'] if release else [])],
                                   env=env, capture_output=True, timeout=90)
            results.append((built.returncode, built.stdout, built.stderr,
                            output.read_bytes() if built.returncode == 0 else b''))
        assert results[0] == results[1], (source.name, release, results[0][:3], results[1][:3])
        if source.with_suffix('.err').exists():
            assert results[0][0] != 0
        else:
            assert results[0][0] == 0, results[0][2]


def test_checked_evaluator_owns_execution(compiler):  # noqa: F811
    assert b'/compiler/checked_eval.dewy\0' in compiler.read_bytes()
    for name in ('comptime', 'math_comptime'):
        source = (ROOT / f'compiler/{name}.jo').read_text()
        assert not re.search(r'^    (?:if |loop |return )', source, re.M), name
