"""Injected allocation-path failures must leave one cleanup authority per owner."""
import os
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('operation', ['push', 'copy', 'dictionary', 'map_copy'])
def test_owner_growth_failure(compiler, tmp_path, release, operation):
    library = tmp_path / 'lib'
    shutil.copytree(ROOT / 'lib', library)
    runtime = library / 'core/rt.jo'
    text = runtime.read_text()
    if operation == 'map_copy':
        mapping = library / 'core/map.jo'
        text_map = mapping.read_text()
        marker = '        result[key] = __at(m.vals, i)\n'
        assert marker in text_map
        mapping.write_text(text_map.replace(marker,
            '        if i == 1: panic("injected map copy")\n' + marker))
        body = ('let a:dict<Owner Owner>=[Owner[0]->Owner[10] Owner[1]->Owner[11]] '
                'let b=a.copy() printl(b.length)')
        # Four source owners, plus the completed copied first entry.
        expected = 6
    elif operation == 'copy':
        # The source already owns three elements when eager copy allocates.
        marker = '__arr_copy = (p: *u8, es: int) -> *u8:\n'
        assert marker in text
        text = text.replace(marker, marker + '    if es == 16: __panic("injected copy allocation")\n')
        body = 'let a=[Owner[0] Owner[1] Owner[2]] let b=a.copy() printl(b.length)'
        expected = 3
    else:
        # Fail after the capacity check, before relocation. The just-created
        # incoming owner must still be registered alongside the old prefix.
        marker = '    if h[2] >= need: return\n'
        assert marker in text
        text = text.replace(marker, marker + '    if es == 16: __panic("injected growth")\n', 1)
        body = ('let a:array<Owner>=[] loop i in [0..100) {a.push(Owner[i])}'
                if operation == 'push' else
                'let a:dict<int64 Owner>=[] loop i in [0..100) {a[i]=Owner[i]}')
        # __arr_new_raw initially reserves four slots; the fifth is pending.
        expected = 5
    runtime.write_text(text)
    source = tmp_path / 'failure.dewy'
    source.write_text('''Owner=type of [value:int64
    $__drop__
    release=():>void=>{printl"drop"}
''' + ('    $__copy__\n    duplicate=():>Owner=>Owner[value]\n' if operation in ('copy', 'map_copy') else '') + ''']
main=()=>{''' + body + '}\n')
    binary = tmp_path / 'failure'
    built = subprocess.run([compiler, 'build', source, '-o', binary,
                            *(['--release'] if release else [])],
                           env={**os.environ, 'DEWY_CORE_LIB': str(library)},
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 101, ran.stderr
    assert 'injected' in ran.stderr
    assert ran.stdout.splitlines() == ['drop'] * expected
