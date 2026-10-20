"""Scalar contract boundaries: proof, fallback, and erasure on both lowerers."""
import os
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

CASES = ROOT / 'tests/cases/refinements'


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('source', [
    'f=(x:int64):>int64<i => i >? 0>=>x\nmain=()=>printl(f(0))',
    'f=(x:int8<i => i >? 0>):>int8<i => i >? 0>=>x+1\nmain=()=>printl(f(127))',
    'f=(x:uint64):>uint64<i => i <? uint64.max>=>x\nmain=()=>printl(f(18446744073709551615))',
    'change=(@x:int64):>int64=>{x=0;return 1}\nf=(x:int64 y:int64<i => i >? x>):>int64=>y\nmain=()=>{let x:int64=7;let r=f(x change(@x));printl(r)}',
    'value=(x:int64):>int64=>x\nmain=()=>{const limit=value(10);let a:int64<i => i <? limit>=7;if a >? 0 {const limit=value(3);let b:int64<i => i <? limit>=7;printl(b)}}',
])
def test_refinement_runtime_and_strict(compiler, tmp_path, release, source):
    path = tmp_path / 'boundary.dewy'
    path.write_text(source)
    binary = tmp_path / 'boundary'
    result = subprocess.run([compiler, 'build', path, '-o', binary,
                             *(['--release'] if release else [])], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode != 0
    assert 'refinement failed' in ran.stderr
    for command in ('check', 'build'):
        result = subprocess.run([compiler, command, path, *(['-o', binary] if command == 'build' else [])],
                                env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'},
                                capture_output=True, text=True)
        assert result.returncode != 0
        assert 'refinement unknown:' in result.stderr and 'witness' in result.stderr, result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_refinement_proven_erasure(compiler, tmp_path, release):
    path = tmp_path / 'erase.dewy'
    path.write_text('f=(x:int64<i => i >? 0>):>int64<i => i >? 0>=>x\nmain=()=>printl(f(2))')
    result = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'erase', '--ir',
                             *(['--release'] if release else [])], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    bodies = re.findall(r'^fn (?:f_f_|f_main_).*?\n(.*?)(?=^fn |\Z)', result.stdout, re.M | re.S)
    assert bodies
    assert all('__assert_fail' not in body for body in bodies)


@pytest.mark.core_quick
@pytest.mark.parametrize('source,diagnostic', [
    ('main=()=>{let x:int64<i => i >? 0>; printl(x)}', 'refinement refuted'),
    ('main=()=>{let x:int64<i => i >? 0>=1; x=0; printl(x)}', 'refinement refuted'),
    ('f=(x:int64):>int64<i => i =? x>=>{x=0; return x}\nmain=()=>printl(f(3))', None),
    ('main=()=>{let limit:int64=5; let x:int64<i => i <? limit>=1; printl(x)}', 'stable binding'),
    ('f=(@x:int64)=>{x=0}\nmain=()=>{let x:int64<i => i >? 0>=1; f(@x)}', 'mutable refinement'),
    ('f=(x:int64<i => i*i >? 0>)=>printl(x)\nmain=()=>f(2)', 'unsupported refinement term'),
    ('f=(x:int64<i => i >? 0>):>int64=>x\nmain=()=>{let cb:<(x:int64):>int64>=@f; printl(cb(2))}', 'type mismatch'),
])
def test_refinement_rejections(compiler, tmp_path, source, diagnostic):
    path = tmp_path / 'reject.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'build', path, '-o', tmp_path / 'reject'], capture_output=True, text=True)
    if diagnostic:
        assert result.returncode != 0
        assert diagnostic in result.stderr, result.stderr
    else:
        assert result.returncode == 0, result.stderr
        ran = subprocess.run([tmp_path / 'reject'], capture_output=True, text=True)
        assert ran.returncode != 0 and 'refinement failed' in ran.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('name', ['pilot', 'snapshot', 'generic', 'mutate', 'uint',
                                  'recursive', 'local', 'later_dependent'])
def test_refinement_internal_static_positive(compiler, name):
    result = subprocess.run([compiler, 'check', CASES / f'{name}.dewy'],
                            env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.core_quick
def test_refinement_uint_zero_strict(compiler, tmp_path):
    path = tmp_path / 'zero.dewy'
    path.write_text('f=(x:uint64):>uint64=>{let z:uint64=0; return x//z}\nmain=()=>printl(f(2))')
    result = subprocess.run([compiler, 'check', path],
                            env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'},
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'divisor refuted: zero' in result.stderr, result.stderr
