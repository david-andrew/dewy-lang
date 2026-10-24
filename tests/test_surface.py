"""The design surface as the compiler accepts it: directives, zero-argument
member calls, Dewy-native diagnostics and fixed-width shift semantics."""
import os
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.support import target_name

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
        flags += ['--target', target_name(target)]
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
    'assert-unsigned-and-sums': ('''
const big:uint64 = 18446744073709551615
const one:uint64 = 1
main = () => {
    $assert big >? one
    $assert 9223372036854775806 + 1 =? 9223372036854775807
    $assert 40000 * 40000 =? 1600000000
    printl"ok"
}
''', 'ok\n', 0),
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


@pytest.mark.parametrize('name', [pytest.param(name, marks=quick if name == 'runtime-assert-forms' else ())
                                  for name in DIRECTIVE_RUNS])
def test_surface_directive_runs(compiler, tmp_path, name):
    source, expected, code = DIRECTIVE_RUNS[name]
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == code, ran.stdout + ran.stderr
    if code == 0:
        assert ran.stdout == expected
    else:
        assert expected in ran.stdout + ran.stderr


DIRECTIVE_ERRORS = {
    'assert-refuted-message': ('$assert 1 >? 2, "one is small"', 'assertion refuted: one is small'),
    'assert-refuted': ('main = () => { $assert 2 + 2 =? 5 }', 'assertion refuted: this condition is always false'),
    'assert-message-literal': ('main = () => { let m = "x"\n$assert true, m }', 'a `$assert` message is a string literal'),
    'assert-needs-condition': ('main = () => { $assert }', '`$assert` needs a condition'),
    'runtime-assert-refuted': ('main = () => { $runtime_assert 1 =? 2 }', 'assertion refuted'),
    'runtime-assert-bool': ('main = () => { $runtime_assert 3 }', 'expected bool'),
    'no-prelude-setting': ('$no_prelude = true', '`$no_prelude` is part of the design but not implemented yet'),
    'allocator': ('main = () => {\n    let scratch = Arena[]\n    let s = $allocator(scratch) [1 2]\n}', '`$allocator` lends an arena by its place'),
    'unsafe-assume': ('main = () => { $unsafe_assume 1 >? 0 }', '`$unsafe_assume` is part of the design'),
    'expect': ('main = () => { let y = $expect 1 >? 0, "x" }', '`$expect` is a statement'),
    'fail': ('$fail "nope"', '`$fail` belongs in a function'),
    'abstract': ('Tok:type = $abstract type of any & [x:int64]', '`$abstract` is part of the design'),
    'test': ('$test\nlet x = 1', '`$test` marks a module-level function'),
    'proof': ('$proof\nf = () => 1', '$proof bodies allow only'),
    'realtime-reserved': ('main = () => { $realtime\nreturn 0 }', '`$realtime` is reserved for a future bundle'),
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


# ------------------------------------------------- zero-argument member calls

MEMBER_CALL_PROGRAM = '''
Shape:type = [w:int64 h:int64 label:string]
area = (s:Shape):>int64 => s.w * s.h
scaled = (s:Shape factor:int64 = 2):>int64 => area(s) * factor
label = (s:Shape):>string => "function"
main = () => {
    let xs = [3 1 2]
    let last = xs.pop
    printl"{last} {xs.length}"
    xs.push(5)
    printl"{xs.pop()} {xs.length}"
    xs.push(0)
    xs.sort
    printl"{xs[0]} {xs[1]} {xs[2]}"
    xs.clear
    printl"{xs.length}"
    let shape = Shape[2 3 "field"]
    printl"{shape.area} {shape.scaled} {shape.scaled(3)} {shape.area()}"
    printl"{shape.label}"
    let text = "  hi  "
    printl"[{text.trim}] [{text.trim()}] {text.length}"
}
'''


@quick
def test_surface_member_calls(compiler, tmp_path):
    ran = run(compiler, tmp_path, MEMBER_CALL_PROGRAM)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == ['2 2', '5 2', '0 1 3', '0', '6 12 18 6', 'field', '[hi] [hi] 6']


MEMBER_CALL_ERRORS = {
    'builtin-needs-arguments': ('main = () => { let xs = [1]\nxs.push }', "'push' needs arguments: `xs.push(...)`"),
    'function-needs-arguments': ('Shape:type = [w:int64]\ngrow = (s:Shape by:int64):>int64 => s.w + by\n'
                                 'main = () => { let s = Shape[1]\nprintl"{s.grow}" }', "'grow' needs arguments: `s.grow(...)`"),
    'const-receiver': ('main = () => { const xs = [1 2]\nlet x = xs.pop }', "cannot modify const 'xs'"),
}


@pytest.mark.parametrize('name', list(MEMBER_CALL_ERRORS))
def test_surface_member_call_errors(compiler, tmp_path, name):
    source, expected = MEMBER_CALL_ERRORS[name]
    assert expected in diagnose(compiler, tmp_path, source)


# ------------------------------------------------- Dewy-native diagnostics

NATIVE_DIAGNOSTICS = {
    'union-comparison': ('read=(x:int64|string):>bool=>x =? 1.5\nmain=()=>printl(read(1))',
                         'cannot compare int64 | string with float64'),
    'type-names': ('main = () => { let x:string = 3 }', 'expected string, found int'),
    'array-type-name': ('accept=(xs:array<uint8>)=>0\nmain=()=>accept([256])', 'expects array<uint8>'),
    'count-hint': ('main = () => { if 3 { printl"x" } }', '`loop i in [1..3] { }`'),
    'optional-condition': ('f = (xs:array<int64>):>int64? => none\nmain = () => { if f([1]) { printl"x" } }',
                           '`x isnt? none` asks'),
    'collection-condition': ('main = () => { let xs = [1]\nif xs { printl"x" } }', '`xs.length >? 0`'),
    'optional-arithmetic': ('f = (x:int64?) => x + 1\nmain = ():>void => { f(1) }', 'or check it first: `if x isnt? none { ... }`'),
    'optional-order': ('f = (x:int64?) => x <? 1\nmain = ():>void => { f(1) }', 'compared with <?, >?'),
    'union-arithmetic': ('f = (x:int64|string) => x + 1\nmain = ():>void => { f(1) }', '`if x is? int64 { ... }`'),
    'record-operator': ('P:type=[a:int64]\nmain = () => { let p = P[1]\nlet q = p + p }', '`__add__ = (a:P b:P):>P => ...`'),
    'text-plus-number': ('main = () => { let s = "a" + 1 }', 'interpolate, `"a{1}"`'),
    'empty-array': ('main = () => { let m = [] }', '`let m:array<int64> = []`'),
    'real-to-integer': ('main = () => { let x:float64 = 1.5\nlet y:int64 = x }', 'int64(x) makes it a whole number'),
    'union-cast': ('f = (x:int64|string):>int64 => x as int64\nmain = ():>void => { f(1); }', 'inside `if x is? int64 { }`'),
    'array-habit': ('main = () => { let xs = [1 2]\nprintl"{xs.size()}" }', "no 'size' for array<int> (use `.length`)"),
    'dict-habit': ('main = () => { let d:dict<string int64> = ["a"->1]\nprintl"{d.size()}" }', '(use `m.length`)'),
    'type-habit': ('main = () => { let x:float = 1.0 }', "unknown type 'float' (use `float64`"),
    'function-habit': ('f = (x:int64) => { let y = toString(x) }\nmain = ():>void => { f(1) }', '(use `string(x)`)'),
}


@pytest.mark.parametrize('name', [pytest.param(name, marks=quick if name == 'union-comparison' else ())
                                  for name in NATIVE_DIAGNOSTICS])
def test_surface_native_diagnostics(compiler, tmp_path, name):
    source, expected = NATIVE_DIAGNOSTICS[name]
    line = diagnose(compiler, tmp_path, source)
    assert expected in line
    # No Sloppy spellings of types or operators in a Dewy program's diagnostics.
    message = line.split('error:', 1)[1]
    for jo in (' str ', ' str)', '==', '!=', 'u8[]', '-> ', 'if let'):
        assert jo not in message + ' ', (jo, message)


# ------------------------------------------------- fixed-width shift counts

SHIFT_PROGRAM = '''
left=(x:uint64<overflow='wrap'> count:int64):>uint64=>x << count
right=(x:uint64<overflow='wrap'> count:int64):>uint64=>x >> count
signed=(x:int64 count:int64):>int64=>x >> count
narrow=(x:uint8<overflow='wrap'> count:int64):>uint8=>x << count
nsigned=(x:int8 count:int64):>int8=>x >> count
masked=(x:uint64<overflow='wrap'> count:int64):>uint64=>x << (count and 63)
main=():>void=>exit(entry()) entry=():>int64=>{
    loop c in [0 1 7 8 9 63 64 65 127 128 -1] {
        printl"{left(1 c)} {right(18446744073709551615 c)} {signed(-2 c)} {signed(2 c)} {narrow(3 c)} {nsigned(-100 c)} {masked(1 c)}"
    }
    let x:uint64<overflow='wrap'> = 1
    x <<= 64
    let y:int64 = -8
    y >>= 70
    let z:int64 = 5
    z <<= 2
    printl"{x} {y} {z} {int64<overflow='wrap'>(1) << 64} {-2 >> 64} {1 << 3} {(1 << 62) >> 61}"
    return 0
}
'''


def shift_expected():
    mask64 = (1 << 64) - 1

    def wrap(value, bits, signed):
        value &= (1 << bits) - 1
        return value - (1 << bits) if signed and value >> (bits - 1) else value

    lines = []
    for c in [0, 1, 7, 8, 9, 63, 64, 65, 127, 128, -1]:
        u = c & mask64       # counts are unsigned
        lines.append(' '.join(str(v) for v in [
            wrap(1 << u if u < 64 else 0, 64, False),
            mask64 >> u if u < 64 else 0,
            -2 >> min(u, 63), 2 >> min(u, 63),
            wrap(3 << u if u < 64 else 0, 8, False),
            -100 >> min(u, 63),
            wrap(1 << (u & 63), 64, False)]))
    lines.append('0 -1 20 0 -1 8 2')
    return lines


@pytest.mark.parametrize('target', [pytest.param('native', marks=quick), 'wasm', 'linux-arm64'])
@pytest.mark.parametrize('release', [False, True], ids=['debug', 'release'])
def test_surface_wide_shifts(compiler, tmp_path, target, release):
    ran = run(compiler, tmp_path, SHIFT_PROGRAM, target, release)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.splitlines() == shift_expected()



def test_surface_negative_shift_literal(compiler, tmp_path):
    line = diagnose(compiler, tmp_path, 'main = () => { let x:int64 = 3\nprintl"{x << -1}" }')
    assert 'a shift count is unsigned, and -1 is negative' in line
