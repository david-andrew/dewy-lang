"""Checked evaluator: frozen whole-compiler outputs and private instruction ordinals."""
import os
import re
import subprocess

import pytest

from tests import whole_oracle
from tests.support import ROOT, compiler  # noqa: F401
from tests import leaf_oracle


def enum_members(text, name):
    match = re.search(r'^enum '+name+r':([^\n]*)(\n(?:[ \t]+[^\n]*\n)*)?', text, re.M)
    assert match, name
    return re.findall(r'[A-Za-z_]\w*', re.sub(r'#[^\n]*', '', match[1] + (match[2] or '')))


def test_checked_eval_instruction_ordinals():
    owner = (ROOT / 'compiler/checked_eval.dewy').read_text()
    for original, private, table, source in [
        ('IN', 'CXIN', 'intrinsic_kind', 'expr'),
        ('CV', 'CXCV', 'conversion', 'expr'),
        ('Tok', 'Tok', 'token', None),
    ]:
        if source is None:
            expected = (ROOT / 'tests/fixtures/selfhost/token_ordinals.txt').read_text().split()
        else:
            expected = enum_members((ROOT / f'compiler/{source}.jo').read_text(), original)
        entries = re.search(r'^let cx_'+table+r'_values:[^=]*=\[([^\n]*)\]', owner, re.M)
        assert entries
        assert re.findall(private+r'\.(\w+)', entries[1]) == expected


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checked_eval_twins(compiler, tmp_path, release):  # noqa: F811
    sources = [ROOT / f'tests/cases/comptime/{name}.dewy' for name in
               ('arrays', 'functions', 'control', 'storage', 'semantics', 'interpolation',
                'reflection', 'divide_zero', 'host_effect', 'overflow', 'selfhost_growth', 'shared_writes')]
    env = {**os.environ, 'DEWY_CORE_LIB': str(ROOT / 'lib'), 'DEWY_EMIT_WORKERS': '1'}
    for source in sources:
        output = tmp_path / 'program'
        arguments = ['build', source, '-o', output, *(['--release'] if release else [])]
        built = subprocess.run([compiler, *arguments], env=env, capture_output=True, timeout=90)
        leaf_oracle.check_entry(lambda: whole_oracle.build(
            arguments, built.returncode, built.stdout, built.stderr, [output] if built.returncode == 0 else [], tmp_path))
        if source.with_suffix('.err').exists():
            assert built.returncode != 0
        else:
            assert built.returncode == 0, built.stderr


def test_checked_evaluator_owns_execution(compiler):  # noqa: F811
    assert b'/compiler/checked_eval.dewy\0' in compiler.read_bytes()
    source = (ROOT / 'compiler/comptime.jo').read_text()
    assert not re.search(r'^    (?:if |loop |return )', source, re.M)
