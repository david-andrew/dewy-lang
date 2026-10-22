"""Sparse difference facts survive only universally supported joins."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('body,success', [
    ('if a <? b and b <=? c {$assert a <? c}', True),
    ('if a >=? 0 and a <? 100 {$assert a*2 >=? a; $assert (a+2)*3 =? a*3+6}', True),
    ('if a >=? 0 {$assert a*2 >=? a}', False),
    ('if a <? b and b <=? c {$assert c <? a}', False),
    ('if a >=? 0 and a <? 100 {let x=a+1; $assert x >? a}', True),
    ('if a >=? 0 and a <? 100 {let x=a+1; $assert x =? a}', False),
    ('let x:int64=0; if flag {x=a} else {x=b}; '
     'if a <? c and b <? c {$assert x <? c}', False),
    ('if a <? c and b <? c {let x:int64=0; '
     'if flag {x=a} else {x=b}; $assert x <? c}', True),
    ('if a <? c {let x:int64=0; '
     'if flag {x=a} else {x=b}; $assert x <? c}', False),
])
def test_difference_join(compiler, tmp_path, body, success):
    source = tmp_path / 'relations.dewy'
    source.write_text('probe=(a:int64 b:int64 c:int64 flag:bool)=>{' + body + '}\n'
                      'main=()=>probe(1 2 3 true)\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=30)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if not success:
        assert 'assertion' in result.stderr, result.stderr


@pytest.mark.parametrize('body,success', [
    ('let i:int64=0; loop i <? 10 {$assert i >=? 0; i+=1}; $assert i =? 10', True),
    ('let i:int64=0; loop i <? 0 {i=9}; $assert i =? 0', True),
    ('let i:int64=0; loop i <? 10 {if flag {continue}; i+=1}; $assert i =? 10', True),
    ('let i:int64=0; loop i <? 10 {if flag {i=-1; continue}; $assert i >=? 0; i+=1}', False),
    ('let i:int8=0; loop i <? 127 {$assert i >=? 0; i+=2}', False),
    ('let i:int64=0; loop i <? 10 {if flag {break}; i+=1}; $assert i =? 10', False),
    ('loop i in [0..10) {$assert i >=? 0; $assert i <? 10}', True),
])
def test_loop_validation(compiler, tmp_path, body, success):
    source = tmp_path / 'loops.dewy'
    source.write_text('probe=(flag:bool)=>{' + body + '}\nmain=()=>probe(false)\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=30)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if not success:
        assert 'assertion' in result.stderr, result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('body', [
    'let xs:array<int64>=[1]; loop xs.length >? 0 {xs.clear(); $assert xs.length >? 0}',
    'let i:int64=1; let j:int64=1; loop flag {i=j; j=-1; $assert i >? 0}',
])
def test_loop_invalidations(compiler, tmp_path, body):
    source = tmp_path / 'invalidated.dewy'
    source.write_text('probe=(flag:bool)=>{' + body + '}\nmain=()=>probe(false)\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and 'assertion' in result.stderr, result.stdout + result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_dependent_find(compiler, tmp_path, release):
    source = tmp_path / 'find.dewy'
    source.write_text('''Row:type=[id:int64]
Database:type=[rows:array<Row>]
find=(db:Database id:int64):>int64<i => i <? db.rows.length> | none=>{
    loop i in [0..db.rows.length) {if db.rows[i].id =? id return i}
    return none
}
main=():>void=>exit(entry()) entry=():>int64=>{
    let db=Database[[Row[7]]]
    let found=find(db 7)
    if found is? int64 {$runtime_assert db.rows[found].id =? 7; return 0}
    return 1
}
''')
    result = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'program',
                             *(['--release'] if release else [])],
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    ran = subprocess.run([tmp_path / 'program'], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 0, ran.stderr


@pytest.mark.parametrize('callee,success', [
    ('read=(@x:int64):>int64=>x', True),
    ('read=(@x:int64):>int64=>{x=0; return x}', False),
])
def test_summary_transfer(compiler, tmp_path, callee, success):
    source = tmp_path / 'effects.dewy'
    source.write_text(callee + '\nprobe=(@x:int64)=>{if x >? 0 {read(@x); $assert x >? 0}}\n'
                      'main=()=>{let x:int64=1; probe(@x)}\n')
    result = subprocess.run([compiler, 'check', source], text=True, capture_output=True, timeout=30)
    assert (result.returncode == 0) == success, result.stdout + result.stderr


@pytest.mark.parametrize('stale', [False, True])
@pytest.mark.parametrize('release', [False, True])
def test_strict_index_lane(compiler, tmp_path, stale, release):
    import os
    body = ('if xs.length =? 0 return 0; let i:int64=0; '
            'if i >=? xs.length return 0; xs.clear(); return xs[i]' if stale else 'return xs[i]')
    params = '@xs:array<int64>' if stale else 'xs:array<int64> i:int64'
    actuals = '@xs' if stale else 'xs 0'
    source = tmp_path / 'index.dewy'
    source.write_text(f'forbidden=({params}):>int64=>{{{body}}}\n'
                      f'main=():>void=>exit(entry()) entry=()=>{{let xs:array<int64>=[1]; forbidden({actuals})}}\n')
    arguments = [compiler, 'build', source, '-o', tmp_path / 'program',
                 *(['--release'] if release else [])]
    ordinary = subprocess.run(arguments, text=True, capture_output=True, timeout=30)
    assert ordinary.returncode == 0, ordinary.stderr
    strict = subprocess.run(arguments, text=True, capture_output=True, timeout=30,
                            env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})
    assert strict.returncode != 0, strict.stdout
    assert ('index is not in bounds' if stale else 'cannot prove index is in bounds') in strict.stderr, strict.stderr


@pytest.mark.parametrize('source', [
    '''xs:array<int64>=[1]
Marker:type=[]
__as__=(m:Marker):>string=>{xs.clear(); return "x"}
probe=()=>{if xs.length >? 0 {let text="{Marker[]}"; $assert xs.length >? 0}}
main=()=>probe()
''',
    '''resize=(@xs:array<int64>):>bool=>{xs.clear(); return true}
probe=(@xs:array<int64>)=>{loop xs.length >? 0 and resize(@xs) {$assert xs.length >? 0}}
main=()=>{let xs:array<int64>=[1]; probe(@xs)}
''',
    'let y:int64=1\nprobe=(@x:int64 flag:bool)=>{if x >? 0 {loop flag {y=0; $assert x >? 0}}}\n'
    'main=()=>{let x:int64=1; probe(@x false)}\n',
    # (six nested counters exhaust the loop budget; an exhausted loop proves nothing)
    'probe=(n:int64)=>{' + ''.join(f'let {v}:int64=0;loop {v} <? n {{' for v in 'abcdef') +
    'f+=1}' + ''.join(f'{v}+=1}}' for v in 'edcba') + '$assert a >=? 0}\nmain=()=>probe(2)\n',
])
def test_loop_hidden_and_exhausted(compiler, tmp_path, source):
    path = tmp_path / 'hidden.dewy'
    path.write_text(source)
    result = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30)
    assert result.returncode != 0 and 'assertion' in result.stderr, result.stdout + result.stderr
