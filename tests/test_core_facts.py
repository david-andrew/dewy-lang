"""Finalization, scalar-policy harness and erasure checks for the pilot goldens."""
import os
import re
import subprocess

import pytest

from tools.cases import match_patterns
from tests.support import ROOT, compiler  # noqa: F401

CASES = ROOT / 'tests/cases/facts'


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_scalar_fact_erasure(compiler, tmp_path, release):
    source = tmp_path / 'erasure.dewy'
    original = (CASES / 'erasure.dewy').read_text()
    bodies = []
    for assertions in (True, False):
        source.write_text(original if assertions else re.sub(r'^.*\$assert.*$', '', original, flags=re.M))
        built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program', '--ir',
                                *(['--release'] if release else [])],
                               text=True, capture_output=True, timeout=30)
        assert built.returncode == 0, built.stdout + built.stderr
        body = re.search(r'^fn f_kernel_.*?\n(.*?)(?=^fn |\Z)', built.stdout, re.M | re.S)
        assert body, 'keep the kernel emitted for an instruction-for-instruction comparison'
        bodies.append(body[1])
    assert bodies[0] == bodies[1], 'symbolic assertions changed runtime IR'


@pytest.mark.parametrize('name', ['unknown_parameter', 'write_after_guard', 'later_operand',
                                  'shared_capture', 'nonlinear', 'erased_call', 'join_one_sided',
                                  'mutable_alias', 'opaque_arm', 'erased_message', 'budget', 'wrap_unknown'])
def test_scalar_fact_check_diagnostics(compiler, name):
    result = subprocess.run([compiler, 'check', CASES / f'{name}.dewy'],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode != 0
    patterns = (CASES / f'{name}.err').read_text().splitlines()
    assert not match_patterns(patterns, result.stdout + result.stderr), result.stdout + result.stderr


@pytest.mark.parametrize('command', ['check', 'build'])
@pytest.mark.parametrize('name,expected', [('guarded_division', None),
                                          ('policy_unknown', 'cannot prove divisor is nonzero: missing bound'),
                                          ('policy_refuted', 'divisor refuted: zero'),
                                          ('policy_math_result', 'cannot prove division result: possible fixed-width wrap')])
def test_scalar_fact_internal_policy(compiler, tmp_path, command, name, expected):
    arguments = [compiler, command, CASES / f'{name}.dewy']
    if command == 'build':
        arguments += ['-o', tmp_path / 'program']
    result = subprocess.run(arguments, env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'},
                            text=True, capture_output=True, timeout=30)
    if expected:
        assert result.returncode != 0
        assert expected in result.stdout + result.stderr, result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_scalar_fact_erased_capture(compiler, tmp_path, release):
    built = subprocess.run([compiler, 'build', CASES / 'erased_capture.dewy',
                            '-o', tmp_path / 'program', '--ir',
                            *(['--release'] if release else [])],
                           text=True, capture_output=True, timeout=30)
    assert built.returncode != 0
    assert 'erased operand would introduce a runtime capture' in built.stderr
    assert not re.search(r'^fn ', built.stdout, re.M), 'failed erasure proof reached lowering'
