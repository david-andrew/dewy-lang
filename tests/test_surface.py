"""The design surface as the compiler accepts it: directives, zero-argument
member calls, Dewy-native diagnostics and fixed-width shift semantics."""
import os
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

quick = pytest.mark.core_quick


@pytest.fixture(scope='module')
def compiler():
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER to the experimental source-level core')
    return Path(value).resolve(strict=True)


class Scripts(HTMLParser):
    """Extract the generated web runner, which Node can execute."""

    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.inside = self.inside or tag == 'script'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def run(compiler, tmp_path, source, target='native', release=False):
    """Build and run one program; return the finished process."""
    runner = None
    if target != 'native':
        runner = shutil.which('qemu-aarch64' if target == 'linux-arm64' else 'node')
        if runner is None:
            pytest.skip(f'runner unavailable for {target}')
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    binary = tmp_path / 'main'
    flags = ['--release'] if release else []
    if target != 'native':
        flags += ['--target', target]
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=60, check=False)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'linux-arm64':
        command = [runner, binary]
    elif target == 'wasm':
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        script = tmp_path / 'main.cjs'
        script.write_text('\n'.join(scripts.parts))
        command = [runner, script]
    return subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)


def diagnose(compiler, tmp_path, source):
    """Check a program that must be rejected; return its first error line."""
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode != 0, 'accepted:\n' + source
    errors = [line for line in checked.stderr.splitlines() if 'error:' in line]
    assert errors, checked.stderr
    return errors[0]


# ---------------------------------------------------------------- directives

DIRECTIVE_RUNS = {
    'runtime-assert-forms': ('''
check = (x:int64 ys:array<int64>):>int64 => {
    $runtime_assert x >=? 0
    $runtime_assert(x <? 100)
    $runtime_assert (ys.length >? 0), "need {x} items"
    $runtime_assert(x =? x, "same")
    return x + ys[0]
}
main = () => printl"{check(2 [40])}"
''', '42\n', 0),
    'runtime-assert-failure': ('''
check = (x:int64):>int64 => {
    $runtime_assert x >=?   0
    return x
}
main = () => printl"{check(-1)}"
''', 'assertion failed: x >=? 0', 101),
    'runtime-assert-message': ('''
check = (x:int64):>int64 => {
    $runtime_assert x >=? 0, "negative {x}"
    return x
}
main = () => printl"{check(-3)}"
''', 'negative -3', 101),
    'runtime-assert-call-message': ('''
main = () => {
    let x = 5
    $runtime_assert(x =? 4, "x is {x}")
}
''', 'x is 5', 101),
    'static-assert-constants': ('''
const limit = 10
const name = "dewy"
$assert limit >? 3
$assert limit * 2 =? 20, "doubled"
$assert name =? "dewy" and not (name =? "jo")
$assert(limit not=? 0, "nonzero")
main = () => {
    const local = 4
    $assert local + limit =? 14
    let value:(int64|string) = 3
    if value is? int64 {
        $assert value is? int64
        printl"{value + local}"
    }
}
''', '7\n', 0),
    'loop-label-kept': ('''
main = () => {
    let total = 0
    $rows
    loop i in [0..3) {
        loop j in [0..3) {
            if j =? 1 { continue $rows }
            if i =? 2 { break $rows }
            total += 10
        }
    }
    printl"{total}"
}
''', '20\n', 0),
}


@pytest.mark.parametrize('name', [pytest.param(name, marks=quick) for name in DIRECTIVE_RUNS])
def test_surface_directive_runs(compiler, tmp_path, name):
    source, expected, code = DIRECTIVE_RUNS[name]
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == code, ran.stdout + ran.stderr
    if code == 0:
        assert ran.stdout == expected
    else:
        assert expected in ran.stdout + ran.stderr


DIRECTIVE_ERRORS = {
    'assert-unknown-local': ('main = () => { let x = 3\n$assert x >? 1 }',
                             'cannot prove assertion yet: `x` is not a compile-time constant'),
    'assert-unknown-call': ('main = (args:array<string>) => { $assert args.length >? 0 }',
                            'cannot prove assertion yet: it depends on a function call'),
    'assert-refuted-message': ('$assert 1 >? 2, "one is small"', 'assertion refuted: one is small'),
    'assert-refuted': ('main = () => { $assert 2 + 2 =? 5 }', 'assertion refuted: this condition is always false'),
    'assert-real': ('main = () => { $assert 1.5 <? 2.0 }', 'cannot prove assertion yet: real-number'),
    'assert-message-literal': ('main = () => { let m = "x"\n$assert true, m }', 'a `$assert` message is a string literal'),
    'assert-needs-condition': ('main = () => { $assert }', '`$assert` needs a condition'),
    'runtime-assert-refuted': ('main = () => { $runtime_assert 1 =? 2 }', 'assertion refuted'),
    'runtime-assert-bool': ('main = () => { $runtime_assert 3 }', 'expected bool'),
    'explicit-copies': ('$explicit_copies\nmain = () => 0', '1:1: error: `$explicit_copies` is part of the design but not implemented yet'),
    'no-prelude-setting': ('$no_prelude = true', '`$no_prelude` is part of the design but not implemented yet'),
    'lend': ('main = () => { let bytes = [1u8]\n$lend(bytes) { 1 } }', '`$lend` is part of the design'),
    'allocator': ('main = () => { let s = $allocator(@scratch) [1 2] }', '`$allocator` is part of the design'),
    'unsafe-assume': ('main = () => { $unsafe_assume 1 >? 0 }', '`$unsafe_assume` is part of the design'),
    'expect': ('main = () => { $expect 1 >? 0, "x" }', '`$expect` is part of the design'),
    'fail': ('main = () => { $fail "nope" }', '`$fail` is part of the design'),
    'breakpoint': ('main = () => { $breakpoint }', '`$breakpoint` is part of the design'),
    'target': ('main = () => { printl"{$target}" }', '`$target` is part of the design'),
    'abstract': ('Tok:type = $abstract type of any & [x:int64]', '`$abstract` is part of the design'),
    'test': ('$test\nf = () => 1', '`$test` is part of the design'),
    'proof': ('$proof\nf = () => 1', '`$proof` is part of the design'),
    'prototype-in-block': ('main = () => { $prototype\nreturn 0 }', '`$prototype` is part of the design'),
    'field': ('main = () => { let p = [x = 1]\nprintl"{p.$field("x")}" }', '`$field` is part of the design'),
    'unknown-label': ('main = () => { $foo\nreturn 0 }',
                      'a loop label must be followed by a loop (`$foo` is not a directive)'),
    'unknown-setting': ('$frob = 3', 'unknown directive `$frob`'),
    'capture-outside-parameters': ('main = () => { $capture }', '`$capture` belongs in a parameter list'),
}


@pytest.mark.parametrize('name', [pytest.param(name, marks=quick if name in {'assert-unknown-local', 'explicit-copies', 'assert-refuted'} else ())
                                  for name in DIRECTIVE_ERRORS])
def test_surface_directive_errors(compiler, tmp_path, name):
    source, expected = DIRECTIVE_ERRORS[name]
    assert expected in diagnose(compiler, tmp_path, source)
