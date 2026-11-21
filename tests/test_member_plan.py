"""A single checked member body agrees with expanded checking, proofs and lowering."""
import os
import platform
import subprocess

import pytest

from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401


CASES = ROOT / 'tests/cases/member_template'
FRONTEND = ROOT / 'tests/ladder/99_dewy_frontend/design.dewy'
TRACE = (b'member template ', b'member lowering ', b'member facts ', b'member syntax rejected ')
NATIVE_X64 = platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64')


def invoke(compiler, source, mode, *args):
    env = os.environ | {'DEWY_MEMBERS': mode, 'DEWY_CORE_LIB': str(ROOT / 'lib'),
                        'DEWY_EMIT_WORKERS': '1'}
    result = subprocess.run([compiler, *args[:1], source, *args[1:]], env=env,
                            capture_output=True, timeout=90)
    lines = result.stderr.splitlines(keepends=True)
    trace = [line for line in lines if line.startswith(TRACE)]
    diagnostics = b''.join(line for line in lines if not line.startswith(TRACE))
    return (result.returncode, result.stdout, diagnostics), b''.join(trace)


@pytest.mark.skipif(not NATIVE_X64, reason='single-body native lowering is enabled on Linux x64')
@pytest.mark.parametrize('source,loops', [(FRONTEND, 2), (CASES / 'ordered_columns.dewy', 1)])
def test_member_plan_native_image(compiler, tmp_path, source, loops):
    output = tmp_path / 'program'
    expanded, _ = invoke(compiler, source, 'expanded', 'build', '-o', output)
    assert expanded[0] == 0, expanded
    expected = output.read_bytes()
    output.unlink()
    candidate, trace = invoke(compiler, source, 'trace', 'build', '-o', output)
    assert candidate == expanded
    assert trace.count(b'one parameterized body') == loops, trace
    assert output.read_bytes() == expected
    reference, _ = invoke(compiler, source, 'reference', 'check', '--obligations')
    assert invoke(compiler, source, '', 'check', '--obligations')[0] == reference


@pytest.mark.parametrize('name,fallback', [('partial_conversion', b'false, 0 locals'),
                                           ('partial_byte_proof', b'decided again')])
def test_member_plan_later_diagnostic(compiler, name, fallback):
    source = CASES / (name + '.dewy')
    for command in [('check', '--obligations'), ('check',)]:
        expanded, _ = invoke(compiler, source, 'reference', *command)
        assert expanded[0] != 0
        candidate, trace = invoke(compiler, source, 'trace', *command)
        assert candidate == expanded
        assert fallback in trace, trace


@pytest.mark.skipif(not NATIVE_X64, reason='single-body native lowering is enabled on Linux x64')
def test_member_plan_comptime_materializes(compiler, tmp_path):
    source = CASES / 'comptime_members.dewy'
    output = tmp_path / 'program'
    candidate, trace = invoke(compiler, source, 'trace', 'build', '-o', output)
    assert candidate[0] == 0, candidate
    assert b'member lowering' in trace and b'one parameterized body' not in trace
    assert subprocess.check_output([output], timeout=30) == source.with_suffix('.out').read_bytes()


def test_member_plan_twins(compiler, tmp_path, monkeypatch):
    cases = ['member_template/comptime_members', 'member_template/ordered_columns', 'member_template/partial_conversion',
             'member_template/partial_byte_proof', 'tests/ladder/99_dewy_frontend/design.dewy']
    assert compare_facts(compiler, tmp_path, monkeypatch, cases,
                         leaves=('member_plan', 'member_admit', 'facts_members', 'member_ops', 'isolation_ops')) == 3
