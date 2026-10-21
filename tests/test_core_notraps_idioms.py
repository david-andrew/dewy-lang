"""Everyday partial-operation idioms prove under the no-traps (require-static) policy.

Each PROVED function is one idiom; each REJECTED program keeps an invalidation
or a missing fact that must still be reported.
"""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVED = {
    # A nonzero length is at least one: `xs[0]` and `xs[end]` after an early return.
    'nonzero_length': '''peek=(xs:array<int64>):>int64=>{
    if xs.length =? 0 return 0
    return xs[0]+xs[end]+xs[xs.length-1]
}
main=():>int64=>peek([1 2])
''',
    'nonzero_scalar': '''last=(xs:array<int64> k:int64):>int64=>{
    if k <? 0 or k not=? xs.length return 0
    if k =? 0 return 0
    return xs[k-1]
}
main=():>int64=>last([1 2] 2)
''',
    # Element and field writes in a loop body keep the lengths they cannot change.
    'element_writes_keep_length': '''shift=(xs:array<int64>):>array<int64>=>{
    let out=xs
    loop i in [1..out.length) {out[i]=out[i-1]}
    loop i in [0..xs.length) {
        let bad=xs
        bad[i]=bad[i]+1
    }
    return out
}
main=():>int64=>shift([1 2 3]).length
''',
    'field_writes_keep_length': '''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world.ids[i]=world.ids[i]+1
        world.score+=1
    }
    return world.score
}
main=():>int64=>tick(World[[1 2] 0])
''',
}

REJECTED = {
    'guard_without_exit': ('''peek=(xs:array<int64>):>int64=>{
    if xs.length =? 0 {printl"empty"}
    return xs[0]
}
main=():>int64=>peek([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'pop_after_guard': ('''peek=(xs:array<int64>):>int64=>{
    let ys=xs
    if ys.length =? 0 return 0
    ys.pop()
    return ys[0]
}
main=():>int64=>peek([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'resize_in_loop': ('''drain=(xs:array<int64>):>int64=>{
    let ys=xs
    let t=0
    loop i in [0..ys.length) {
        ys.pop()
        t+=ys[i]
    }
    return t
}
main=():>int64=>drain([1])
''', 'cannot prove index is in bounds: missing upper bound'),
    'field_resize_in_loop': ('''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world.ids.clear()
        world.ids[i]=1
    }
    return 0
}
main=():>int64=>tick(World[[1 2] 0])
''', 'index is not in bounds'),
    'record_replaced_in_loop': ('''World:type=[ids:array<int64> score:int64]
tick=(w:World):>int64=>{
    let world=w
    loop i in [0..world.ids.length) {
        world=World[[] 0]
        world.ids[i]=1
    }
    return 0
}
main=():>int64=>tick(World[[1 2] 0])
''', 'index is not in bounds'),
}


def check(compiler, tmp_path, name, source):
    path = tmp_path / f'{name}.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30,
                          env={**os.environ, 'DEWY_INTERNAL_FACT_POLICY': 'require-static'})


@pytest.mark.parametrize('name', PROVED)
def test_notraps_idiom_proved(compiler, tmp_path, name):
    result = check(compiler, tmp_path, name, PROVED[name])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('name', REJECTED)
def test_notraps_idiom_rejected(compiler, tmp_path, name):
    source, message = REJECTED[name]
    result = check(compiler, tmp_path, name, source)
    assert result.returncode != 0
    assert message in result.stdout + result.stderr, result.stdout + result.stderr
