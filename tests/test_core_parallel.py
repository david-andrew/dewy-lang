"""Dewy callbacks through the worker pool and the serial web fallback."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_core import Scripts

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'examples/parallel_particles.dewy'


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for parallel checks')
    return Path(path).resolve(strict=True)


PROGRAMS = {
    'particles': MODEL.read_text(),
    'matrix-product': '''main=()=>{
let rows=65 let inner=64 let cols=67
let a=reshape([loop i in [0..rows*inner) ((i//inner%3+1)*(i%inner+1)) as float64] rows inner)
let b=reshape([loop i in [0..inner*cols) ((i//cols+1)*(i%cols%5+1)) as float64] inner cols)
let saved=a
let product=a*b
let squares=(inner*(inner+1)*(2*inner+1)//6) as float64
loop i in [0..rows) {loop j in [0..cols) {
    assert(product[i j] =? (i%3+1)*(j%5+1)*squares)
}}
assert(product.shape =? [rows cols] and a.data =? saved.data)
product[0 0]=0.0
assert(a[0 0] =? 1.0 and b[0 0] =? 1.0)
return 0
}''',
    'managed-lifetimes': '''work=():>void=>{
let values=parallel_range(257 (i:int64)=>[name="item {i}" items=[i i+1]])
parallel_update(@values (p)=>{p.items.push(42) p.name+="!" return p})
parallel_map(values (p)=>[p.items p.items]);
}
main=()=>{
work()
let before=alloc_count()
loop round in [0..12) {work()}
assert(alloc_count() =? before)
return 0
}''',
    'managed-values': '''main=()=>{
let words=["one" "two" "three"]
let values=parallel_range(257 (i:int64)=>[name=words[i%3] items=[i i+1]])
let saved=values
parallel_update(@values (p)=>{p.items[0]+=42 p.name+="!" return p})
let sums=parallel_map(values (p)=>sum(p.items))
loop i in [0..values.length) {
    assert(saved[i].items =? [i i+1] and saved[i].name =? words[i%3])
    assert(values[i].items =? [i+42 i+1] and values[i].name =? words[i%3]+"!")
    assert(sums[i] =? 2*i+43)
}
assert(words =? ["one" "two" "three"])
return 0
}''',
    'nested-and-repeated': '''square=(i:int64)=>i*i
main=()=>{
let empty:array<int64>=[]
assert(parallel_map(empty square) =? [])
parallel_update(@empty square)
assert(parallel_range(0 square) =? [])
assert(parallel_range(1 square) =? [0])
loop round in [0..20) {
    let nested=parallel_range(37 (i:int64)=>parallel_range(7 (j:int64)=>i+j))
    loop i in [0..37) {
        loop j in [0..7) { assert(nested[i][j] =? i+j) }
    }
    assert(parallel_range(2 square) =? [0 1])
}
return 0
}''',
}

PROGRAMS['matrix-product-f32'] = PROGRAMS['matrix-product'].replace('float64', 'float32')


@pytest.mark.parametrize('name', PROGRAMS)
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_core_parallel_values(compiler, tmp_path, name, release, target):
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAMS[name])
    output = tmp_path / 'program'
    flags = ['--release'] if release else []
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_EMIT_WORKERS='1', SLOPPY_THREADS='2')
    built = subprocess.run([compiler, 'build', source, '--target', target, '-o', output, *flags],
                           env=env, capture_output=True, text=True, timeout=30, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    args = [output]
    if target == 'wasm':
        node = shutil.which('node')
        assert node, 'Node is required for the web fallback check'
        scripts = Scripts()
        scripts.feed(output.with_suffix('.html').read_text())
        runner = output.with_suffix('.cjs')
        runner.write_text('\n'.join(scripts.parts))
        args = [node, runner]
    modes = [('1', False), ('2', False)] if target == 'native' else [('1', False)]
    if target == 'native' and name.startswith('matrix-product'):
        modes.append(('2', True))
    for threads, no_avx in modes:
        env['SLOPPY_THREADS'] = threads
        if no_avx:
            env['SLOPPY_NO_AVX'] = '1'
        result = subprocess.run(args, env=env, capture_output=True, text=True,
                                timeout=15, check=False)
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('body', [
    'let total=0\nmain=()=>{parallel_range(10 (i:int64)=>{total+=i return i}); return 0}',
    'main=()=>{let total=0 parallel_range(10 (i:int64)=>{total+=i return i}); return 0}',
    'let total=0\nchange=(i:int64)=>{total+=i return i}\nmain=()=>{parallel_range(10 change); return 0}',
    'let total:array<int64>=[]\nmain=()=>{parallel_range(10 (i:int64)=>{total.push(i) return i}); return 0}',
])
def test_core_parallel_rejects_shared_writes(compiler, tmp_path, body):
    source = tmp_path / 'invalid.dewy'
    source.write_text(body)
    result = subprocess.run([compiler, 'check', source], capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode != 0
    assert 'parallel_range' in result.stderr and 'total' in result.stderr, result.stderr
