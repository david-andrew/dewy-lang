"""Lifecycle hooks and structural ownership survive generic instantiation."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('copyable', [False, True])
def test_generic_owner_hooks(compiler, tmp_path, release, copyable):
    source = tmp_path / 'generic.dewy'
    source.write_text('''drops:int64=0
copies:int64=0
let Handle:type=<T>[value:T
    $__drop__
    release=():>void=>{drops+=1}
''' + ('''    $__copy__
    duplicate=():>Handle<T>=>{copies+=1 Handle<T>[value]}
''' if copyable else '') + ''']
let Box:type=<T>[value:T]
forward=<T>(value:T):>T=>value
exercise=()=>{
    let first=Handle<int64>[7]
    let box:Box<Handle<int64>>=[value=first]
    let moved=forward(box)
''' + ('''    let snapshot=moved.copy()
    $runtime_assert snapshot.value.value=?7
''' if copyable else '') + '''    $runtime_assert moved.value.value=?7
    let other=Handle<bool>[true]
    $runtime_assert other.value
}
main=()=>{
    exercise()
    printl"{drops} {copies}"
}
''')
    binary = tmp_path / 'generic'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == ('3 1\n' if copyable else '2 0\n')


@pytest.mark.parametrize('release', [False, True])
def test_generic_function_rejects_owner_copy(compiler, tmp_path, release):
    source = tmp_path / 'copy.dewy'
    source.write_text('''let Handle:type=<T>[value:T
    $__drop__
    release=():>void=>{}
]
duplicate=<T>(value:T):>[first:T second:T]=>[first=value second=value]
main=()=>{let pair=duplicate(Handle<int64>[7]) printl"{pair.first.value}"}
''')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'copy',
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode != 0
    assert 'cannot copy a move-only owner' in built.stderr
