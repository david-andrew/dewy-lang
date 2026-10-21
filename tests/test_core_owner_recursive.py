"""Recursive ownership keeps completed copies live across box allocation failure."""
import os
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('fail_at, expected', [(2, 2), (3, 4), (4, 5)])
def test_recursive_owner_allocation_failure(compiler, tmp_path, release, fail_at, expected):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    runtime = library / 'core/rt.jo'
    text = runtime.read_text()
    marker = '__box_new = (size: int) -> *u8:\n'
    assert marker in text
    text = text.replace(marker, 'owner_box_allocations: int\n' + marker +
        f'    owner_box_allocations += 1\n    if owner_box_allocations == {fail_at}: __panic("injected box allocation")\n')
    runtime.write_text(text)
    source = tmp_path / 'failure.dewy'
    source.write_text('''Leaf=type of [value:int64
    $__drop__
    release=():>void=>{printl"drop"}
    $__copy__
    duplicate=():>Leaf=>Leaf[value]
]
Node:type=[next:Node?=none owner:Leaf]
main=()=>{
    let first=Node[none Leaf[1]]
    let second=Node[first Leaf[2]]
    let third=Node[second Leaf[3]]
    let snapshot=third.copy()
}
''')
    binary = tmp_path / 'failure'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           env={**os.environ, 'DEWY_CORE_LIB': str(library)},
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 101, ran.stderr
    assert 'injected box allocation' in ran.stderr
    assert ran.stdout.splitlines() == ['drop'] * expected
