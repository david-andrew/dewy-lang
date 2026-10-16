"""Checked scalar-record arrays can use inline storage without changing values.

Execution is opt-in while the representation is experimental. The planner
test uses the ordinary source-driver path, independently of that switch.
"""
import os
import subprocess
from pathlib import Path

import pytest
from driver_artifacts import compiler_driver

from tools.sloppy_bridge.run import compile_program
from udewy.cache import cache_artifact

ROOT = Path(__file__).resolve().parents[2]


def test_dense_element_plan_is_global_and_preserves_unsupported_abis(tmp_path):
    source = tmp_path / 'element-plan.dewy'
    source.write_text(f'''
from reporting import Span
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/type_queries.dewy'}" as views
import p"{ROOT / 'dewy/bootstrap/backend/udewy/elements.dewy'}" as elements
import p"{ROOT / 'dewy/bootstrap/backend/udewy/layouts.dewy'}" as layouts
main=():>int64=>{{
    let table=types.Table[]
    let word=types.primitive('int64' @table)
    let boolean=types.primitive('bool' @table)
    let pair=types.object_type([types.ObjectField['x' word] types.ObjectField['y' word]] none false [] [] @table)
    let pairs=types.array_type(pair none @table)
    let small=types.object_type([types.ObjectField['flag' boolean]] none false [] [] @table)
    types.array_type(small none @table);
    let nested=types.object_type([types.ObjectField['values' pairs]] none false [] [] @table)
    types.array_type(nested none @table);
    let plan=elements.select([] layouts.Context[] @table)
    $runtime_assert pair in? plan.dense and small in? plan.dense
    $runtime_assert plan.dense[pair].size =? 16 and plan.dense[small].size =? 1
    $runtime_assert nested not in? plan.dense
    let loc=Span[0 0]
    let array=hir.ExpressedIdentifier[loc pairs 'items']
    let sorted=elements.select([array hir.ArrayMethod[loc word 0 'sort']] layouts.Context[] @table)
    $runtime_assert pair not in? sorted.dense and small in? sorted.dense
    let raw=elements.select([array hir.Transmute[loc word 0]] layouts.Context[] @table)
    $runtime_assert pair not in? raw.dense
    let narrow=types.object_type([types.ObjectField['x' word]] none false [] [] @table)
    let narrowed=types.array_type(narrow none @table)
    let cast=elements.select([array hir.ValueCast[loc narrowed 0]] layouts.Context[] @table)
    $runtime_assert pair not in? cast.dense and narrow not in? cast.dense
    views.dict_type(word pair @table);
    let dictionary=elements.select([] layouts.Context[] @table)
    $runtime_assert pair not in? dictionary.dense and small in? dictionary.dense
    return 42
}}
''')
    binary = compiler_driver('dense-element-plan', source, tmp_path)
    run = subprocess.run([binary], capture_output=True, timeout=15, check=False)
    assert run.returncode == 42, (run.returncode, run.stdout, run.stderr)


CASES = {
    'copy-grow-place': '''
Pair:type=[x:int64 y:int64]
write=(@pair:Pair):>void=>{pair.x=99}
main=():>int64=>{
    let xs:array<Pair>=[Pair[20 22]]
    let other=xs.copy
    let saved=xs[0]
    loop i in 0..100 {xs.push(Pair[i i])}
    $runtime_assert xs.length >? 0
    write(@xs[0])
    $runtime_assert other.length >? 0
    if xs[0].x not=? 99 or other[0].x not=? 20 or saved.x not=? 20 return 1
    return saved.x+other[0].y
}
''',
    'insert-pop-truncate': '''
Pair:type=[x:int64 y:int64]
main=():>int64=>{
    let xs:array<Pair>=[Pair[1 2] Pair[20 22] Pair[3 4]]
    xs.insert(Pair[5 6] 1)
    $runtime_assert xs.length >? 2
    let removed=xs.pop(2)
    $runtime_assert xs.length >? 1
    xs[1]=Pair[7 8]
    xs.truncate(1)
    xs.clear
    xs.push(Pair[9 10])
    if removed.x not=? 20 or removed.y not=? 22 return 1
    return removed.x+removed.y
}
''',
    'narrow-fields-spread': '''
Small:type=[flag:bool x:int8 y:uint16]
main=():>int64=>{
    let xs:array<Small>=[Small[true (-12) 250] Small[false 3 400]]
    let ys:array<Small>=[xs... Small[true 4 1000]]
    $runtime_assert xs.length >? 0 and ys.length >? 2
    xs[0].x=7
    if not ys[0].flag or ys[0].x not=? -12 or ys[1].flag or ys[2].y not=? 1000 return 1
    let sum:int64=0
    loop item in ys {sum+=item.x as int64}
    return if sum =? -5 42 else 2
}
''',
    'returned-snapshot': '''
Pair:type=[x:int64 y:int64]
first=(items:array<Pair>):>Pair=>{$runtime_assert items.length >? 0 return items[0]}
main=():>int64=>{
    let xs:array<Pair>=[Pair[20 22]]
    let saved=first(xs)
    xs.clear
    loop i in 0..100 {xs.push(Pair[i i])}
    return saved.x+saved.y
}
''',
    'array-alias-arguments': '''
Entry:type=[value:int64]
Bag:type=[items:array<Entry>]
observe=(before:array<Entry> @bag:Bag):>int64=>{
    $runtime_assert before.length >? 0 and bag.items.length >? 0
    bag.items[0].value=9
    return before[0].value
}
main=():>int64=>{
    let bag=Bag[[Entry[7]]]
    let seen=observe(bag.items @bag)
    $runtime_assert bag.items.length >? 0
    return if seen =? 7 and bag.items[0].value =? 9 42 else 1
}
''',
}


@pytest.mark.parametrize('route', ['native', 'bridge'])
@pytest.mark.parametrize('name', CASES)
def test_dense_record_values(tmp_path, monkeypatch, route, name):
    compiler = os.environ.get('DEWY_DENSE_TEST_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_DENSE_TEST_COMPILER to a compiler with the dense experiment')
    emitter = os.environ.get('DEWY_SLOPPY_EMITTER')
    if route == 'bridge' and not emitter:
        pytest.skip('set DEWY_SLOPPY_EMITTER for the alternate backend')
    source = tmp_path / f'{name}.dewy'
    source.write_text(CASES[name])
    monkeypatch.setenv('DEWY_DENSE_RECORDS', '1')
    if route == 'bridge':
        binary, _ = compile_program(source, Path(compiler), Path(emitter), tmp_path, release=True)
    else:
        env = {**os.environ, 'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_FAILURE_LOG': '0'}
        result = subprocess.run([compiler, '-c', str(source)], cwd=tmp_path, env=env,
                                capture_output=True, text=True, timeout=90, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        binary = tmp_path / cache_artifact(source, cwd=tmp_path)
    run = subprocess.run([binary], capture_output=True, timeout=15, check=False)
    assert run.returncode == 42, (run.returncode, run.stdout, run.stderr)
