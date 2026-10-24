"""The `panics` effect: code that may fail a runtime check or otherwise panic.
A no-traps scope cannot call it unless it opts in with `$runtime_checks`;
`& no panics` forbids it; library preconditions are the caller's obligations."""
import subprocess
import time

import pytest

from tests.support import compiler  # noqa: F401

REJECTED = {
    # A dependency built with `$runtime_checks` cannot crash inside a caller that did not opt in.
    'checked_dependency': ('''$runtime_checks=false
helper=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
main=():>void=>printl(helper([1 2] 1))
''', '6:23: error: calling `helper` may panic (helper: runtime check: index is in bounds'),
    # An explicit check is a panic too (here not assumed the module's own
    # handling), and a handle to it may be called.
    'handle': ('''$runtime_checks=false
$assume_local_asserts=false
check=(x:int64):>int64=>{
    $runtime_assert(x >? 0)
    return x
}
apply=(f:<(x:int64):>int64> x:int64):>int64=>f(x)
main=():>void=>printl(apply(@check 2))
''', 'a handle to `check`, which may be called, may panic (check: `$runtime_assert`'),
    # A row excluding panics holds transitively, whatever the scope.
    'row': ('''loose=(xs:array<int64> i:int64):>int64=>xs[i]
strict=(xs:array<int64>):>int64 & no panics=>loose(xs 0)
main=():>void=>printl(strict([1]))
''', "error: effect contract violation in 'strict': it may panic, and its row excludes panics; strict -> loose: runtime check"),
    'granted': ('bad=(x:int64):>int64 & panics=>x\nprintl(bad(1))\n',
                '`panics` is inferred, never granted: a row can only exclude it, `& no panics`'),
    # The strict lane excludes panics; the repair names its opt-out.
    'bundle': ('''$no_hidden_costs
$assume_local_asserts=false
pick=(x:int64):>int64=>{
    $no_hidden_costs=false
    $runtime_checks
    $runtime_assert(x >? 0)
    return x
}
twice=(x:int64):>int64 & no panics=>pick(x)*2
main=()=>{
    $no_hidden_costs=false
    $runtime_checks
    printl(twice(3))
}
''', 'opt this function out of `$no_hidden_costs` with `$no_hidden_costs=false` and add `$runtime_checks`'),
    # Library preconditions are the caller's obligations.
    'first_unproven': ('$runtime_checks=false\nf=(xs:array<int64>)=>printl(xs.first)\nf([1])\n',
                       'cannot prove refinement `xs.length >? 0`'),
    'swap_unproven': ('$runtime_checks=false\nf=(@xs:array<int64> i:int64)=>xs.swap(0 i)\nlet a:array<int64>=[1 2]\nf(@a 1)\n',
                      'cannot prove index is in bounds'),
    'insert_unproven': ('$runtime_checks=false\nf=(@xs:array<int64> i:int64)=>xs.insert(5 i)\nlet a:array<int64>=[1]\nf(@a 0)\n',
                        'cannot prove index is in bounds'),
    # A literal format specification the library accepts cannot fail; this one can.
    'format_spec': ('$runtime_checks=false\nshow=(s:string):>string=>format(s ".2")\nprintl(show("x"))\n',
                    'calling `format` may panic (format: panic "text formatting takes alignment'),
    'dictionary': ('$runtime_checks=false\ncount=(d:dict<string int64>):>int64=>d["a"]\nprintl(count(["a"->1]))\n',
                   'cannot prove the key is in the dictionary'),
}

PROVED = '''$runtime_checks=false
edit=(@xs:array<int64> i:int64):>void=>{
    if 0 <=? i and i <=? xs.length {xs.insert(5 i)}
    xs.insert(7 0)
    if xs.length >? 1 {xs.swap(0 xs.length-1)}
}
ends=(xs:array<int64>):>int64 & no panics=>if xs.length >? 0 xs.first+xs.last else 0
main=():>void=>{
    let a:array<int64>=[1]
    edit(@a 0)
    printl("{a} {ends(a)} {ends([])} {a.first(2)}")
}
'''


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_panics_rejected(compiler, tmp_path, name):
    source, expected = REJECTED[name]
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode != 0 and expected in result.stderr, result.stderr


def test_panics_proved(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVED, 'run')
    assert result.returncode == 0 and result.stdout == '[1 5 7] 8 0 [1 5]\n', result.stdout + result.stderr


def test_format_literal_spec(compiler, tmp_path):
    source = '$runtime_checks=false\nshow=(x:float64 n:int64 s:string):>string=>"{format(x ".6f")} {format(n ",")} {format(n "#x")} {format(s ">8")} {format(x "8.2%")}"\nprintl(show(0.5 1234567 "hi"))\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '0.500000 1,234,567 0x12d687       hi   50.00%\n', result.stdout + result.stderr


def test_panics_opted_in(compiler, tmp_path):
    # The caller's own `$runtime_checks` accepts the call; the check runs.
    source = '''helper=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
main=():>void=>{
    $runtime_checks
    printl(helper([1 2] 1))
    printl(helper([1 2] 5))
}
'''
    result = run(compiler, tmp_path, '$runtime_checks=false\n' + source, 'run')
    assert result.stdout == '2\n' and result.returncode == 101, result.stdout + result.stderr


def test_panics_listing(compiler, tmp_path):
    # `check --obligations` names library calls that may panic where checks are allowed.
    source = '$runtime_checks\nshow=(s:string):>string=>format(s ".2")\nprintl(show("x"))\ncount=(d:dict<string int64>):>int64=>d["a"]\nprintl(count(["a"->1]))\n'
    result = run(compiler, tmp_path, source, 'check', '--obligations')
    assert 'program.dewy:2:26: may panic: calling `format` ($runtime_checks)' in result.stdout, result.stdout + result.stderr
    # (a missing key is the caller's obligation, listed as its own check)
    assert 'program.dewy:4:38: runtime check: the key is in the dictionary ($runtime_checks)' in result.stdout, result.stdout + result.stderr


def test_first_runtime_check(compiler, tmp_path):
    # Where checks are allowed, an empty array fails the precondition at the call.
    source = 'f=(xs:array<int64>)=>printl(xs.first)\nf([])\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 101 and 'refinement failed: `xs.length >? 0`' in result.stderr, result.stderr


HOVERED = '''$runtime_checks=false
helper=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    return xs[i]
}
total=(xs:array<int64>):>int64=>xs.length
main=():>void=>{
    $runtime_checks
    printl(helper([1 2] 1) + total([1]))
}
'''


def test_panics_hover(tmp_path):
    # The editor shows the inferred effect on a function that may panic.
    from tests.test_core_editor_features import Client, at, compiler_path, hover_text
    path = tmp_path / 'hovered.dewy'
    path.write_text(HOVERED)
    client = Client(compiler_path(), tmp_path)
    try:
        diagnostics = client.set_text(path.as_uri(), HOVERED, 1)
        assert not [d for d in diagnostics if d['severity'] == 1], diagnostics
        # (the quiet-time check with lowering settles the effect)
        time.sleep(3)
        assert 'helper=(xs:array<int64> i:int64):>int64 & panics' in hover_text(client, at(path, HOVERED, 'helper([', 0))
        assert '& panics' not in hover_text(client, at(path, HOVERED, 'total([', 0))
    finally:
        client.close()
