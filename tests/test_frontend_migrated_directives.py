"""`$target` and `$build` values and folded chains (spliced in a block, a value elsewhere), record
literal methods, collectors, `$field` rows and record comprehensions, `$test(cases=…)`,
`$supported_targets`, transfer rows, positional aliases, intersections, effect parameters and
rows on function types, stepped range values, pattern renames and signed loop elements, as the
direct parser reads them, build as the reference grammar and projection build them, and report
the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = r'''$runtime_checks
$supported_targets = ["x86_64-linux" "aarch64-linux" "wasm32"]
if $target =? "wasm32" {
    width = ():>int64 => 32
} else {
    width = ():>int64 => 64
}
Entry:type = [int64 string]
Located:type = [line:int64 column:int64]
Labeled:type = [label:string]
Tagged:type = Located & Labeled & [extra:bool = false  show = ():>string => "{extra}"]
Raw:type = [p:int64 $send $sync=false]
Action:type = <E:Effect>(<(x:int64):>int64 & E>)
apply_one = <E:Effect>(f:Action<E> value:int64):>int64 & E => f(value)
square = (x:int64):>int64 & no_effects => x * x
newline = ():>string => if $target.os =? 'windows' "\r\n" else "\n"
evens = 0,2..10
$test(cases=[[a=1 b=2] [a=(-3) b=4]])
commutes = (a:int64 b:int64):>void => {
    $expect a + b =? b + a
}
f = ():>int64 => 5
copy_fields = <T>(value:T) => [loop field in fields(T) $field(field.name)=value.$field(field.name)]
main = () => {
    if $build.mode =? 'debug' and $target.arch in? ["x86_64" "aarch64" "wasm32"] {
        let mode = "known"
    } else {
        let mode = "other"
    }
    let bits = if $target.arch in? ["riscv64" "c"] {0} else {width() * 2}
    let counter = [value=1 step = () => (value += 1)]
    counter.step()
    let collected = [f(); 7 {3 4} if bits >? 0 5]
    let named = [$field("answer")=42]
    let t:Tagged = [line=3 column=4 label="x"]
    let e:Entry = [1 "a"]
    let parent = [loop c in [1 2 3] -1]
    let [line as l  column:int64 as c] = Located[line=1 column=2]
    printl("{mode} {bits} {counter.value} {collected} {named.answer} {t.show()} {e[1]} {parent} {l + c}")
    printl("{newline().length} {apply_one(@square 3)} {evens} {copy_fields(Located[5 6]).line} {$target.length >? 2}")
}
'''


def test_direct_directives_identity(compiler, tmp_path):
    source = tmp_path / 'forms.dewy'
    source.write_text(PROGRAM)
    images, outputs = [], []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        result = subprocess.run([compiler, 'build', source, '-o', output],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, timeout=10)
        assert ran.returncode == 0
        outputs.append(ran.stdout)
    assert images[0] == images[1]
    assert outputs[0] == outputs[1]
    assert b'known 128 2 [7 3 4 5] 42' in outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('', 'if $target.arch =? "arm" {printl(1)}'), ('', 'printl(if $target =? "wasm" 1 else 2)'),
    ('if $target.os =? "macos" {\ng = () => 1\n}', ''), ('', 'printl($build.debug)'),
    ('$supported_targets = ["x86_64"]', ''), ('$supported_targets = ["riscv64-linux"]', ''),
    ('$test(cases=())\nt = (a:int64):>void => {}', ''), ('$test(cases=[1 2])\nt = ():>void => {}', ''),
    ('', 'printl([1; 2])'), ('', 'printl([x=1 {2 3}])'), ('R:type = [n:int64 $send=1]', ''),
    ('A:type = [a:int64]\nB:type = A & int64 & ~0', ''), ('', 'let [a as [b] c] = [[1] 2]'),
    ('', 'let r = [loop i in xs $field("a")=i 3]'), ('', 'let o = [f=() => g  g=1]')])
def test_migrated_directives_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nf0 = ():>void => {{}}\nmain=():>void=>{{\nlet xs = [1]\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
