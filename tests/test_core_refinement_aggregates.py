"""Aggregate refinement boundaries preserve storage authority and snapshots."""
import os
import subprocess

import pytest
from tests.support import ROOT, compiler  # noqa: F401


def build(compiler, tmp_path, source, *, strict=False, release=False):
    path = tmp_path / 'aggregate.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'build', path, '-o', tmp_path / 'aggregate',
                           *(['--release'] if release else [])], text=True, capture_output=True,
                          env={**os.environ, **({'DEWY_INTERNAL_FACT_POLICY': 'require-static'} if strict else {})})


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('source', [
    'R:type=[score:int64<i => i >=? 0>]\nf=(@r:R)=>{r.score+=1}\nmain=()=>{let r=R[9223372036854775807]; f(@r)}',
    'f=(x:int64)=>{let xs:array<int64<i => i >? 0>>=[1]; xs[0]=x}\nmain=()=>f(0)',
])
def test_runtime_store(compiler, tmp_path, source, release):
    result = build(compiler, tmp_path, source, release=release)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode != 0 and 'refinement failed' in ran.stderr, ran.stderr


@pytest.mark.parametrize('source,diagnostic', [
    ('R:type=[score:int64<i => i >? 0>]\nmain=()=>{let r:R;printl(r.score)}', 'is read before it is given a value'),
    ('f=(@x:int64)=>{x=0}\nR:type=[score:int64<i => i >? 0>]\nmain=()=>{let r=R[1];f(@r.score)}', 'mutable refinement'),
    ('f=(@x:int64)=>{x=0}\nmain=()=>{let xs:array<int64<i => i >? 0>>=[1];f(@xs[0])}', 'mutable refinement'),
    ('main=()=>{let xs:array<int64<i => i >? 0>>=[0];printl(xs.length)}', 'refinement refuted'),
])
def test_rejected_store(compiler, tmp_path, source, diagnostic):
    result = build(compiler, tmp_path, source)
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('source', [
    'main=()=>{let xs:array<int64<i => i >? 0> length=1>=[1]; printl(xs[0])}',
    'main=()=>{let xs:array<int64<i => i >? 0>?>=[]; printl(xs.length)}',
    'R:type=[score:int64<i => i >=? 0>]\nmain=()=>{let r=R[1];let saved=r.copy();r.score=2;$assert saved.score =? 1;$assert r.score =? 2}',
    'main=()=>{let xs:array<array<int64>>=[[1 2]];xs[0]=[];$assert xs.length =? 1;$assert xs[0].length =? 0}',
    'main=()=>{let xs:array<int64>=[1 2];xs.reserve(100);$assert xs.length =? 2}',
])
def test_aggregate_positive(compiler, tmp_path, source):
    result = build(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('source,valid', [
    ('R:type=[low:int64 high:int64<i => i >=? low>]\nmain=()=>{let r=R[1 3];r.low=4}', False),
    ('R:type=[low:int64 high:int64<i => i >=? low>]\nmain=()=>{let r=R[1 3];r.low=2;$runtime_assert r.high =? 3}', True),
    ('R:type=[low:int64=2 high:int64<i => i >=? low>=low]\nmain=()=>{let r=R[];$runtime_assert r.high =? 2}', True),
    ('R:type=[low:int64 high:int64<i => i >=? low>]\nf=(@x:int64)=>{x=4}\nmain=()=>{let r=R[1 3];f(@r.low)}', False),
    ('main=()=>{let xs:array<int64 length <? 3>=[1 2];xs.push(3)}', False),
    ('main=()=>{let xs:array<int64 length <? 3>=[1];xs.push(3);$assert xs.length =? 2}', True),
    ('main=()=>{let xs:array<int64<i => i >? 0> length=2>;printl(xs[0])}', False),
])
def test_dependent_store(compiler, tmp_path, source, valid):
    result = build(compiler, tmp_path, source)
    if not valid:
        assert result.returncode != 0, result.stderr
        assert 'refinement' in result.stderr, result.stderr
        return
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('release', [False, True])
def test_dynamic_length_runtime(compiler, tmp_path, release):
    source = 'f=(@xs:array<int64 length <? 3>)=>{xs.push(3)}\nmain=()=>{let xs:array<int64 length <? 3>=[1 2];f(@xs)}'
    result = build(compiler, tmp_path, source, release=release)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode != 0 and 'refinement failed' in ran.stderr, ran.stderr


@pytest.mark.parametrize('source', [
    'main=()=>{let xs:array<array<int64>>=[[1]];xs=[[2 3]];$assert xs[0].length =? 1}',
    'f=(i:int64 j:int64)=>{let xs:array<int64>=[1 2];if i >=? 0 and i <? 2 and j >=? 0 and j <? 2 {$runtime_assert xs[i] >? 0;xs[j]=0;$assert xs[i] >? 0}}\nmain=()=>f(0 0)',
    'f=(n:int64)=>{let xs:array<int64>=[1];loop n >? 0 {xs.push(2);n-=1};$assert xs.length =? 1}\nmain=()=>f(1)',
])
def test_invalidated_projection(compiler, tmp_path, source):
    result = build(compiler, tmp_path, source)
    assert result.returncode != 0, result.stderr
    assert 'assertion' in result.stderr, result.stderr


def test_stale_index_lane_policy(compiler, tmp_path):
    source = 'f=(@xs:array<int64>):>int64=>{if xs.length =? 0 return 0;let i:int64=0;if i >=? xs.length return 0;xs.clear();return xs[i]}\nmain=()=>{let xs:array<int64>=[1];printl(f(@xs))}'
    result = build(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode != 0 and 'bounds' in ran.stderr, ran.stderr
    result = build(compiler, tmp_path, source, strict=True)
    assert result.returncode != 0 and 'index is not in bounds' in result.stderr, result.stderr


@pytest.mark.parametrize('source', [
    'change=(@xs:array<int64>):>int64=>{xs.clear();return 7}\nmain=()=>{let xs:array<int64>=[1 2];xs.push(change(@xs));$runtime_assert xs.length =? 1}',
    'change=(@xs:array<int64>):>int64=>{xs.clear();xs.push(9);return 0}\nmain=()=>{let xs:array<int64>=[1 2];let value=xs[change(@xs)];$runtime_assert xs.length =? 1}',
    'change=(@xs:array<int64>):>int64=>{xs.clear();return 0}\nf=(saved:array<int64 length =? 2> ignored:int64)=>printl(saved.length)\nmain=()=>{let xs:array<int64>=[1 2];f(xs change(@xs))}',
])
def test_operand_snapshots(compiler, tmp_path, source):
    result = build(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('value,success', [(1, True), (0, False)])
def test_structural_conversion(compiler, tmp_path, value, success):
    source = f'main=()=>{{let source=[score={value}];let checked:[score:int64<i => i >? 0>]=source;printl(checked.score)}}'
    result = build(compiler, tmp_path, source)
    assert (result.returncode == 0) == success, result.stderr
    if not success:
        assert 'refinement refuted' in result.stderr
    else:
        ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == '1', ran.stderr


@pytest.mark.parametrize('source', [
    'R:type=[xs:array<int64> index:addr<i => i <? xs.length>]\nmain=()=>{let r=R[[1] 0];r.xs.clear()}',
    'S:type=[value:int64]\nR:type=[sub:S high:int64<i => i >=? sub.value>]\nmain=()=>{let r=R[S[1] 3];r.sub.value=4}',
])
def test_projected_sibling_mutation(compiler, tmp_path, source):
    result = build(compiler, tmp_path, source)
    assert result.returncode != 0 and 'refinement refuted' in result.stderr, result.stderr


def test_addr_target_bound(compiler, tmp_path):
    source = tmp_path / 'target.dewy'
    source.write_text('main=()=>{let i:addr=4294967296;printl(i)}')
    native = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    web = subprocess.run([compiler, 'build', source, '--target', 'wasm32', '-o', tmp_path / 'web'], capture_output=True, text=True)
    assert native.returncode == 0, native.stderr
    assert web.returncode != 0 and 'refinement refuted' in web.stderr, web.stderr


@pytest.mark.parametrize('source,success', [
    ('main=()=>{let xs:array<int64<i => i >? 0>>=[1];loop @x in xs {x=0}}', False),
    ('main=()=>{let xs:array<int64>=[1 2];let saved=xs.copy();xs[0]=8;$assert saved[0] =? 1;$assert xs.length =? 2}', True),
    ('f=(saved:array<int64 length =? 2> ignored:int64)=>printl(saved.length)\nmain=()=>{let xs:array<int64>=[1 2];let change=($capture @xs)=>{xs.clear();return 0};f(xs change())}', True),
])
def test_alias_and_callback_authority(compiler, tmp_path, source, success):
    result = build(compiler, tmp_path, source)
    assert (result.returncode == 0) == success, result.stderr
    if success:
        ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
    else:
        assert 'refinement refuted' in result.stderr, result.stderr


@pytest.mark.parametrize('source,diagnostic', [
    ('f=(limit:int64 xs:array<int64<i => i <? limit>>)=>printl(xs.length)\nmain=()=>f(3 [1])', 'instantiated storage authority'),
    ('f=(limit:int64):>[value:int64<i => i <? limit>]=>[value=1]\nmain=()=>printl(f(3))', 'dependencies must name siblings'),
])
def test_uninstantiated_authority_rejected(compiler, tmp_path, source, diagnostic):
    result = build(compiler, tmp_path, source)
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr


def test_refined_compound_selector_once(compiler, tmp_path):
    source = 'next=(@i:int64):>int64=>{let old=i;i+=1;return old}\nmain=()=>{let i:int64=0;let xs:array<int64<n => n >? 0>>=[1 2];xs[next(@i)]+=1;$runtime_assert i =? 1;$runtime_assert xs[0] =? 2;$runtime_assert xs[1] =? 2}'
    result = build(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    ran = subprocess.run([tmp_path / 'aggregate'], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('source', [
    'main=()=>{let x:int64<i => i >? 0>=1;let y:int64=2;[x y]=[0 3];printl(x)}',
])
def test_unpack_storage_authority(compiler, tmp_path, source):
    result = build(compiler, tmp_path, source)
    assert result.returncode != 0 and 'refinement refuted' in result.stderr, result.stderr
