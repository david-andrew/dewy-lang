"""Scoped settings: the obligation listing, prototype warnings, editor hints and bundles."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SITES = '''checked=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
guarded=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    if i >=? 0 and i <? xs.length return xs[i]
    return 0
}
draft=(xs:array<int64> i:int64):>int64=>{
    $prototype
    return xs[i]
}
main=()=>{
    $runtime_checks
    let xs:array<int64>=[1 2 3]
    printl(int(checked(xs 0)) + guarded(xs 1) + draft(xs 2))
}
'''
# (outside those scopes an unproven index is a compile error: no hidden trap)
LOOSE = 'loose=(xs:array<int64> i:int64):>int64=>xs[i]\nmain=()=>printl(loose([1] 0))\n'


def run(compiler, tmp_path, source, *arguments, env=None):
    path = tmp_path / 'sites.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path,
                          env=env)


@pytest.mark.core_quick
def test_obligation_listing(compiler, tmp_path):
    result = run(compiler, tmp_path, SITES, 'check', '--obligations')
    assert result.returncode == 0, result.stderr
    # Proven obligations vanish; each other site names what makes it a runtime check.
    assert result.stdout.splitlines() == [
        'sites.dewy:3:12: runtime check: index is in bounds: missing lower and upper bounds ($runtime_checks)',
        'sites.dewy:12:12: runtime check: index is in bounds: missing lower and upper bounds ($prototype)',
    ]
    assert result.stderr.count('prototype: cannot prove index is in bounds') == 1, result.stderr
    assert 'sites.dewy:12:12: warning: prototype:' in result.stderr
    plain = run(compiler, tmp_path, SITES, 'check')
    assert plain.returncode == 0 and plain.stdout == '', plain.stderr
    loose = run(compiler, tmp_path, LOOSE, 'check', '--obligations')
    assert loose.returncode != 0 and 'sites.dewy:1:41: error: cannot prove index is in bounds' in loose.stderr, loose.stderr


def test_prototype_warnings_silenced(compiler, tmp_path):
    source = '$prototype\n$prototype_warnings=false\nat=(xs:array<int64> i:int64):>int64=>xs[i]\nmain=()=>printl(at([4] 0))\n'
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode == 0 and 'prototype:' not in result.stderr, result.stderr
    built = run(compiler, tmp_path, source.replace('$prototype_warnings=false\n', ''), 'check')
    assert built.returncode == 0 and 'warning: prototype: cannot prove index is in bounds' in built.stderr


def test_editor_hint_for_runtime_checks(compiler, tmp_path):
    path = tmp_path / 'sites.dewy'
    path.write_text(SITES)
    env = dict(os.environ, DEWY_LOWER='1')
    result = subprocess.run([compiler, 'lsp', '--dump', path], text=True, capture_output=True, timeout=60, env=env)
    hints = [line.split('\t')[2] for line in result.stdout.splitlines() if line.startswith('I\t')]
    # Only `$runtime_checks` sites are hinted; prototype sites are warnings already.
    assert hints == ['runtime check: index is in bounds: missing lower and upper bounds'], result.stdout[:2000]


def test_user_bundle(compiler, tmp_path):
    source = '''$careful = {
    $explicit_copies
    $runtime_checks=false
}
safe=(xs:array<int64> i:int64):>int64=>{
    $careful
    if i >=? 0 and i <? xs.length return xs[i]
    return 0
}
main=()=>printl(safe([5 6] 1))
'''
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode == 0, result.stderr
    rejected = run(compiler, tmp_path, source.replace('    if i >=? 0 and i <? xs.length return xs[i]\n', '    return xs[i]\n'),
                   'check')
    assert rejected.returncode != 0 and 'cannot prove index is in bounds' in rejected.stderr, rejected.stderr
    conflict = run(compiler, tmp_path, source.replace('    $careful\n', '    $careful\n    $runtime_checks\n'), 'check')
    assert 'not allowed inside `$careful`, which sets `$runtime_checks=false`' in conflict.stderr, conflict.stderr


@pytest.mark.parametrize('source,diagnostic', [
    ('$quiet = {\n    printl("x")\n}\nmain=()=>0\n', 'a bundle lists settings'),
    ('$quiet = {\n    $frob\n}\nmain=()=>0\n', 'a bundle lists builtin settings'),
    ('$quiet = {\n    $default_row = 3\n}\nmain=()=>0\n', 'effect'),
    ('$runtime_checks = {\n    $prototype\n}\nmain=()=>0\n', 'takes a literal true or false'),
    ('$no_hidden_costs = {\n    $prototype\n}\nmain=()=>0\n', 'the bundle `$no_hidden_costs` is already defined'),
])
def test_bundle_definition_errors(compiler, tmp_path, source, diagnostic):
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr
