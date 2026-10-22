"""Mutable slice calls prove disjointness and keep their storage borrowed."""
import subprocess

import pytest

from tests.support import compiler

SWAP = '''
swap=(@a:array<int64> @b:array<int64>):>void=>{
 loop i in [0..a.length) {let v=a[i] a[i]=b[i] b[i]=v}
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_mutable_adjacent_slices(compiler, tmp_path, release):
    source = tmp_path / 'slices.dewy'
    source.write_text(SWAP + '''
main=()=>{
 let a:array<int64>=[1 2 3 4]
 let saved=a
 let mid:int64=2
 swap(@a[..mid) @a[mid..])
 assert(a =? [3 4 1 2] and saved =? [1 2 3 4])
 swap(@a[..0) @a[0..0))
 assert(a =? [3 4 1 2])
 return 0
}
''')
    output = tmp_path / 'slices'
    build = subprocess.run([compiler, 'build', source, '-o', output,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([output], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('arguments', [
    '@a[..3) @a[2..]', '@a[..mid] @a[mid..]', '@a[..mid) @a[..mid)',
    '@a @a[..mid)', '@a[..mid+1) @a[mid..]',
])
def test_overlapping_mutable_slices_rejected(compiler, tmp_path, arguments):
    source = tmp_path / 'overlap.dewy'
    source.write_text(SWAP + '''main=()=>{
 let a:array<int64>=[1 2 3 4]
 let mid:int64=2
 swap(''' + arguments + ''')
 return 0
}''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert run.returncode != 0
    assert 'overlap' in run.stderr, run.stderr


@pytest.mark.parametrize('body', ['a.push(8)', 'a=[8]', 'let copy=a printl"{copy}"'])
def test_mutable_slice_cannot_resize_or_escape(compiler, tmp_path, body):
    source = tmp_path / 'escape.dewy'
    source.write_text('change=(@a:array<int64>):>void=>{' + body + '''}
main=():>void=>{let a:array<int64>=[1 2] change(@a[..1))}
''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert run.returncode != 0
    assert 'mutable slice callee' in run.stderr, run.stderr

FORK = '''
walk=(@a:array<int64> @scratch:array<int64>):>void=>{
 let n=a.length
 if n =? 0 return
 if n =? 1 {a[0]+=1 scratch[0]=a[0]*2 return}
 let mid=n//2
 let _joined=parallel_range(2 ($capture @a $capture @scratch i:int64):>int64=>{
  if i =? 0 {walk(@a[..mid) @scratch[..mid))}
  else {walk(@a[mid..] @scratch[mid..])}
  return 0
 })
}
main=()=>{
 let a:array<int64>=[loop i in [0..2049) i as int64]
 let scratch:array<int64>=[loop i in [0..2049) 0 as int64]
 let saved=a
 loop round in [0..3) {walk(@a @scratch)}
 loop i in [0..2049) {assert(a[i] =? saved[i]+3 and scratch[i] =? 2*a[i])}
 return 0
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_mutable_slice_fork(compiler, tmp_path, release):
    import os
    source = tmp_path / 'fork.dewy'
    source.write_text(FORK)
    output = tmp_path / 'fork'
    build = subprocess.run([compiler, 'build', source, '-o', output,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    for workers in (1, 2):
        run = subprocess.run([output], env=dict(os.environ, SLOPPY_THREADS=str(workers)),
                             capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('replacement', ['@a[..mid+1)', '@a[mid..]', '@a[..mid]'])
def test_mutable_slice_fork_rejects_overlap(compiler, tmp_path, replacement):
    source = tmp_path / 'overlap_fork.dewy'
    source.write_text(FORK.replace('@a[..mid)', replacement))
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert run.returncode != 0
    assert 'proven-disjoint scoped fork' in run.stderr, run.stderr


def test_mutable_slice_capture_cannot_escape(compiler, tmp_path):
    source = tmp_path / 'escape_capture.dewy'
    source.write_text('''
escape=(@a:array<int64>)=>($capture @a):>int64=>a[0]
main=():>void=>{let a:array<int64>=[1] let f=escape(@a) printl"{f()}"}
''')
    run = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert run.returncode != 0
    assert 'proven-disjoint scoped fork' in run.stderr, run.stderr

READ_FORK = '''
copy=(src:array<int64> @out:array<int64> first:int64):>void=>{
 let n=out.length
 if n <=? 8 {loop i in [0..n) {out[i]=src[first+i]+1} return}
 let mid=n//2
 let _joined=parallel_range(2 ($capture src $capture @out i:int64):>int64=>{
  if i =? 0 {copy(src @out[..mid) first)}
  else {copy(src @out[mid..] first+mid)}
  return 0
 })
}
main=()=>{
 let src:array<int64>=[loop i in [0..1031) i as int64]
 let out=src
 copy(src @out[..] 0)
 loop i in [0..1031) {assert(src[i] =? i and out[i] =? i+1)}
 return 0
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_readonly_input_shared_by_disjoint_fork(compiler, tmp_path, release):
    import os
    source = tmp_path / 'read_fork.dewy'
    source.write_text(READ_FORK)
    binary = tmp_path / 'read_fork'
    build = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    for workers in (1, 2):
        run = subprocess.run([binary], env=dict(os.environ, SLOPPY_THREADS=str(workers)),
                             capture_output=True, text=True, timeout=30)
        assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('change', ['src[0]=99', 'src.push(99)', 'let saved=src'])
def test_readonly_borrow_cannot_be_mutated_or_copied(compiler, tmp_path, change):
    source = tmp_path / 'read_escape.dewy'
    source.write_text(READ_FORK.replace('let n=out.length', change+'\n let n=out.length'))
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'mutable slice callee' in result.stderr, result.stderr


def test_read_and_write_slice_overlap_rejected(compiler, tmp_path):
    source = tmp_path / 'read_overlap.dewy'
    source.write_text(READ_FORK.replace('copy(src @out[..] 0)', 'copy(src @src[..] 0)'))
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'overlap' in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('body', [
    'loop i in [0..a.length+1) {b[i]=a[i]}',
    'let i:int64=0 loop i <? a.length {b[i]=a[i] i+=2}',
    'let j:int64=0 j-=1 b[j]=a[0]',
])
def test_borrowed_bounds_still_trap(compiler, tmp_path, release, body):
    source = tmp_path / 'bounds.dewy'
    source.write_text('copy=(@a:array<int64> @b:array<int64>):>void=>{' + body + '''}
main=():>void=>{let a:array<int64>=[1 2 3] let b:array<int64>=[0] copy(@a[..] @b[..])}
''')
    result = subprocess.run([compiler, *(['--release'] if release else []), source],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'out of bounds' in result.stderr, result.stderr
