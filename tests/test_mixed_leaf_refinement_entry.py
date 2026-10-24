"""A Sloppy caller's narrowing fallback may summarize a mutable Dewy leaf."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_mutable_leaf_summary_entry(compiler, tmp_path, release):
    (tmp_path / 'leaf.dewy').write_text('''$runtime_checks
Kind:type='nil' | 'value'
Node:type=[kind:Kind='nil' child:int32=0]
clone=(@store:array<Node> n:int64):>int64=>{
    if n =? 0 {return 0}
    let node=store[n]
    let c=store.length
    store.push(node)
    if node.child not=? 0 {store[c].child=int32(clone(@store node.child))}
    c
}
''')
    source = tmp_path / 'driver.jo'
    source.write_text('''use 'leaf.dewy'
main = ():
    store = [Node(), Node(kind = .value), Node(kind = .value, child = 1)]
    result = i32(clone(store, 2))
    print("{result} {store.len()} {store[int(result)].child}")
''')
    binary = tmp_path / 'driver'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '3 5 4\n'
