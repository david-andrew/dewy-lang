"""Parallel loop syntax, nested calls, and deterministic indexed collection."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import Scripts, target_name


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for parallel loop checks')
    return Path(path).resolve(strict=True)


PROGRAM = '''main=():>void=>{
let empty:array<int64>=[]
assert([parallel x in empty x*x] =? [])
assert([parallel i in [3..3) i] =? [])
assert([parallel i in [5,3..0] i] =? [5 3 1])
assert([parallel i in (0..4] i] =? [1 2 3 4])
let values=[loop i in [0..129) [name="item {i}" data=[i i+1]]]
let original=values
parallel @value in values {value.name="{value.name}!" value.data[0]+=10}
parallel i in [0..129) {
    assert(values[i].name =? "item {i}!" and original[i].name =? "item {i}")
    assert(values[i].data[0] =? i+10 and original[i].data[0] =? i)
}
loop round in [0..12) {
    let result=[parallel i in [0..37) [parallel j in [0..41) [value=i+j text="{i}:{j}"]]]
    loop i in [0..37) {loop j in [0..41) {
        assert(result[i][j] =? [value=i+j text="{i}:{j}"])
    }}
}
let floats:array<float64>=[1e16 1.0 -1e16 2.0]
loop round in [0..20) {assert(sum([parallel x in floats x]) =? sum(floats))}
}'''


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True])
def test_parallel_syntax(compiler, tmp_path, target, release):
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAM)
    output = tmp_path / 'main'
    env = dict(os.environ, SLOPPY_THREADS='2', SLOPPY_EMIT_WORKERS='1')
    built = subprocess.run([compiler, 'build', source, '-o', output, '--target', target_name(target),
                            *(['--release'] if release else [])], env=env,
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [output]
    if target == 'wasm':
        scripts = Scripts()
        scripts.feed(output.with_suffix('.html').read_text())
        runner = output.with_suffix('.cjs')
        runner.write_text('\n'.join(scripts.parts))
        command = ['node', runner]
    for threads in (1, 2):
        env['SLOPPY_THREADS'] = str(threads)
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('body,diagnostic', [
    ('let total=0 parallel i in [0..10) {total+=i}', 'captured'),
    ('let xs=[0 0] parallel i in [0..2) {xs[0]=i}', 'captured'),
    ('parallel i in [0..10) {return i}', 'return cannot leave'),
    ('parallel i in [0..10) {break}', 'cannot leave'),
    ('parallel i in [0..10) {continue}', 'cannot leave'),
    ('parallel true {}', 'bounded iterable'),
    ('parallel x in [1 2] {x+=1}', 'cannot modify parameter'),
])
def test_parallel_obligations(compiler, tmp_path, body, diagnostic):
    source = tmp_path / 'invalid.dewy'
    source.write_text('main=():>void=>{' + body + '}')
    result = subprocess.run([compiler, 'check', source], capture_output=True,
                            text=True, timeout=30)
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr
