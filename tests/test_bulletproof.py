"""`$bulletproof` (lib/directives.dewy; docs/design/assumptions.md): the strictest-everything
bundle. A program under it compiles only when every obligation is proven, and each member's
guarantee holds under it. Bundles include other bundles, transitively."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, command='check', name='main.dewy'):
    (tmp_path / name).write_text(source)
    return subprocess.run([compiler, command, name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


# Every index and narrowing proven, functions without a row of their own get
# `no allocates & no panics`, and main handles OutOfMemory.
PROVEN = '''$bulletproof
total = (xs:array<int64 length=4>):>int64 => {
    let t:int64 = 0
    loop i in [0..4) {
        let v = xs[i]
        if v >? -1000 and v <? 1000 t += v
    }
    t
}
main = ():>(void | OutOfMemory) & no panics => {
    let xs:array<int64 length=4> = [1 2 3 4]
    let mean:float64 = float64(total(xs)) / 4.0
    printl"{total(xs)} {mean}"
}
'''


@pytest.mark.core_quick
def test_proven_program_runs(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVEN, 'run')
    assert result.returncode == 0 and result.stdout == '10 2.5\n', result.stdout + result.stderr


MAIN = 'main = ():>(void | OutOfMemory) & no panics => {\n'

# One program per member; each compiles only once its obligation is met, which
# the bundle demands.
MEMBERS = {
    # $no_hidden_costs: no runtime checks
    'index': ('pick = (xs:array<int64 length=4> i:int64):>int64 => xs[i]\n' + MAIN + '    printl(pick([1 2 3 4] 2))\n}\n',
              'error: cannot prove index is in bounds'),
    # $no_hidden_costs: functions without a row of their own do not allocate
    'row': ('grow = (n:int64):>int64 => {\n    let xs:array<int64> = []\n    xs.push(n)\n    xs.length\n}\n' + MAIN
            + '    printl(grow(3))\n}\n',
            "effect contract violation in 'grow': allocation exceeds the contract (its row excludes it); grow; witness at main.dewy:4:5; `$bulletproof` gives functions without a row of their own this one"),
    # $no_hidden_costs: $explicit_copies
    'copy': (MAIN + '    let xs:array<int64> = [1]\n    let ys = xs\n    ys[0] = 2\n    printl(xs.length + ys.length)\n}\n',
             'main.dewy:4:14: error: implicit costly copy of array<int64>'),
    # $explicit_allocation_failure: a function that may allocate returns T | OutOfMemory
    'allocation': ('make = (n:int64):>int64 & no panics => {\n    let xs:array<int64> = [n]\n    xs.length\n}\n' + MAIN
                   + '    let k:int64 = make(3)\n    printl(k)\n}\n',
                   'main.dewy:7:19: error: type mismatch: expected int64, found int64 | OutOfMemory'),
    # $finite_floats: $no_inf
    'infinity': (MAIN + '    let x:float64 = float64(args().length)\n    printl(1.0 / x)\n}\n',
                 'main.dewy:4:12: error: cannot prove the divisor is nonzero under `$no_inf`'),
    # $finite_floats: $no_nan
    'nan': (MAIN + '    let x:float64 = float64(args().length) - 3.0\n    printl(sqrt(x))\n}\n',
            "main.dewy:4:12: error: cannot prove the square root's operand is not negative under `$no_nan`"),
    # $no_deadlocks
    'deadlock': ('work = (n:int64):>int64 => n * 2\nmain = ():>void & no panics => {\n    let m = mutex<int64>(0)\n'
                 '    let held = @(m.lock())\n    concurrent {\n        let a = spawn work(21)\n    }\n    held += 1\n}\n',
                 "main.dewy:6:5: error: this joins its tasks while holding 'm' (since line 5), and no certificate covers it (`$no_deadlocks`)"),
    # $assume_local_asserts=false: a `$runtime_assert` makes its own module's callers `panics`
    'local_assert': ('checked = (x:int64):>int64 => {\n    $no_hidden_costs=false\n    $runtime_assert x >? 0\n    x\n}\n'
                     'relay = (x:int64):>(int64 | OutOfMemory) & no blocks => checked(x)\n'
                     'main = () => {\n    $bulletproof=false\n    printl(relay(3))\n}\n',
                     'main.dewy:7:57: error: calling `checked` may panic (checked -> __eaf_checked: `$runtime_assert` at main.dewy:4:5)'),
}


@pytest.mark.parametrize('member', sorted(MEMBERS))
def test_member_guarantee(compiler, tmp_path, member):
    body, diagnostic = MEMBERS[member]
    result = run(compiler, tmp_path, '$bulletproof\n' + body)
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr


def test_local_asserts_only_under_the_bundle(compiler, tmp_path):
    # The same program under the strict lane alone: the module's own asserts are its handling.
    source = '$no_hidden_costs\n' + MEMBERS['local_assert'][0].replace('$bulletproof=false', '$no_hidden_costs=false')
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '3\n', result.stdout + result.stderr


def test_confined_paths(compiler, tmp_path):
    source = ('$bulletproof\n' + MAIN + '    let a = args()\n    if a.length >? 0 {\n        let f = p(a[0])\n'
              '        printl(f.exists)\n    }\n}\n')
    result = run(compiler, tmp_path, source)
    assert result.returncode == 0, result.stderr
    assert 'main.dewy:6:16: warning: `f` is not proven to stay inside a base, which `$confine_external_paths` asks' in result.stderr


def test_opt_out_and_conflict(compiler, tmp_path):
    source = '''$bulletproof
pick = (xs:array<int64> i:int64):>int64 => {
    $bulletproof=false
    $runtime_checks
    xs[i]
}
main = () => {
    $bulletproof=false
    printl(pick([1 2] 1))
}
'''
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '2\n', result.stdout + result.stderr
    conflict = run(compiler, tmp_path, source.replace('    $bulletproof=false\n    $runtime_checks\n', '    $runtime_checks\n'))
    assert ('main.dewy:3:5: error: `$runtime_checks` is not allowed inside `$bulletproof`, which sets `$runtime_checks=false`'
            in conflict.stderr), conflict.stderr


def test_module_policy_needs_a_module(compiler, tmp_path):
    result = run(compiler, tmp_path, 'main = () => {\n    $bulletproof\n    printl(1)\n}\n')
    assert result.returncode != 0 and ('main.dewy:2:5: error: `$bulletproof` includes `$explicit_allocation_failure`, '
                                       'a module policy: put it at the top of a module') in result.stderr, result.stderr


def test_nested_bundles_resolve_in_any_order(compiler, tmp_path):
    # `$outer` includes `$inner`, defined after it; both settings hold where `$outer` is written.
    source = '''$outer = {
    $inner
    $runtime_checks=false
}
$inner = {
    $explicit_copies
}
pick = (xs:array<int64> i:int64):>int64 => {
    $outer
    if i >=? 0 and i <? xs.length return xs[i]
    0
}
main = () => printl(pick([1 2] 1))
'''
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '2\n', result.stdout + result.stderr
    unproven = run(compiler, tmp_path, source.replace('    if i >=? 0 and i <? xs.length return xs[i]\n    0\n', '    xs[i]\n'))
    assert 'main.dewy:10:5: error: cannot prove index is in bounds' in unproven.stderr, unproven.stderr
    copied = run(compiler, tmp_path, source.replace('    $outer\n', '    $outer\n    let ys = xs\n    ys.push(0)\n    printl(xs.length + ys.length)\n'))
    assert 'main.dewy:10:14: error: implicit costly copy' in copied.stderr, copied.stderr


@pytest.mark.parametrize('source,diagnostic', [
    ('$a = {\n    $b\n}\n$b = {\n    $c\n}\n$c = {\n    $a\n}\nmain = () => 0\n',
     'main.dewy:1:1: error: bundles include each other: `$a` includes `$b` includes `$c` includes `$a`'),
    ('$a = {\n    $a\n}\nmain = () => 0\n', 'main.dewy:1:1: error: bundles include each other: `$a` includes `$a`'),
    ('$a = {\n    $no_hidden_costs\n    $no_such_thing\n}\nmain = () => 0\n',
     'main.dewy:3:5: error: unknown member `$no_such_thing` in the bundle `$a`'),
    ('$a = {\n    $no_hidden_costs=false\n}\nmain = () => 0\n',
     'main.dewy:2:5: error: a bundle includes another bundle whole: `$no_hidden_costs`, not `$no_hidden_costs=false`'),
    ('$a = {\n    $no_hidden_costs\n    $runtime_checks\n}\nmain = () => 0\n',
     'main.dewy:2:5: error: `$no_hidden_costs` sets `$runtime_checks=false` in the bundle `$a`, which already sets it on'),
    ('$x = {\n    $default_row = no panics\n}\n$a = {\n    $no_hidden_costs\n    $x\n}\nmain = () => 0\n',
     'main.dewy:6:5: error: the bundle `$a` gets a second `$default_row` from `$x`'),
    ('$a = {\n    $explicit_allocation_failure=false\n}\nmain = () => 0\n',
     'main.dewy:2:5: error: a bundle can turn `$explicit_allocation_failure` on, not off'),
    ('$a = {\n    $no_prelude\n}\nmain = () => 0\n', 'main.dewy:2:5: error: a bundle lists builtin settings'),
])
def test_bundle_member_errors(compiler, tmp_path, source, diagnostic):
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0 and diagnostic in result.stderr, result.stderr
