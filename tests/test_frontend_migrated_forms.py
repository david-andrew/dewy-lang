"""Markers, pipes, word operators, value packs, sequence and shape patterns, literal unions, tuple
and function types, grouped updates, byte strings, broadcast calls, `$clamp`, unpacking
assignments, renames, keyword-only parameters, new axes, bracketed ranges, record spreads, rows,
`??<Kinds>`, dictionary comprehensions, refinement and generic aliases, as the direct parser reads
them, build as the reference grammar and projection build them, and report the same mistakes."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROGRAM = '''$runtime_checks
Sign:type = <-1|0|1>
Mode:type = <'fast' | 1 | 'slow' | 2>
Apply:type = (left:int64 right:int64):>int64
Handler:type = <(x:int64):>int64>
Box:type = <T>(array<T length=2>)
Point:type = [x:int64 y:int64]
small = int64<i => 0 <=? i <=? 10>
NotANumber:type = type of error
K:array<int64> = [3 1 2]
Counter:type = [
    value:int64
    step = () => (value += 1)
]
pair = (a:int64 b:int64):>(int64 int64) => (b a)
classify = (s:-1|0|1):>string => if s =? 1 "positive" else if s =? -1 "negative" else "zero"
shape = (p:Point):>string => match p {
    [x:0 y] => "on the axis at {y}"
    [x y] => "at {x} {y}"
}
bits = (v:int64):>string => match v {
    <0|1> => "bit"
    answer:42 => "the answer {answer}"
    _ => "wide"
}
scale = (value:int64 ... by:int64=2):>int64 => value * by
parse = (text:string):>int64 | NotANumber => if text =? "x" NotANumber else 7
double = (x:int64) => x * 2
main = () => {
    let (a b) = pair(1 2)
    $runtime_assert a =? 2;
    printl("{a} {b} {classify(-1)} {shape(Point[0 5])} {shape(Point[2 3])} {bits(1)} {bits(42)}")
    printl("{21 |> double} {double <| 4} {true nand false} {false nor false} {true xnor true} {~5}")
    let c = Counter[1]
    c.step()
    let apply:Apply = (left:int64 right:int64) => left + right
    let h:Handler = (x:int64) => x + 1
    let box:Box<int64> = [4 5]
    printl("{c.value} {apply(2 3)} {h(1)} {box[1]} {scale(3)} {scale(3 by=4)} {K[0]}")
    let bytes = 0x"0a0b"
    let xs = [1 2 3 4 5]
    printl("{bytes.length} {xs[$clamp 1..10)} {sqrt.([4.0 9.0])} {3 in? (0..5]} {0 in? [..2]} {[1,3..9]}")
    let [p q] = [0 0]
    [p q] = [7 8]
    let [x as first  y] = Point[5 6]
    printl("{p} {q} {first} {y}")
    let m = [1 2 ; 3 4]
    let wide = m[new ..]
    let base = Point[1 2]
    let moved:Point = [base... y=9]
    printl("{m.length} {wide.length} {moved.y} {members(<'a' | 1>).length}")
    let found = parse("x") ??<NotANumber> 0
    let names = [loop n in [1 2 3] n -> n * 10]
    let total = 4 as small
    let text = [104 105] as array<uint8>
    printl("{found} {names.get(2) ?? 0} {total} {text as string ?? "none"} {(text as array<uint8>).read<uint16>(0)}")
}
'''


def test_direct_forms_identity(compiler, tmp_path):
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
    assert b'2 1 negative' in outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('top,body', [
    ('T:type = <0|100>', ''), ('', 'let (a) = (1)'), ('', 'let x = (xs...)'),
    ('f = (... rest:int64) => rest', ''), ('f = (...rest:int64) => rest', ''),
    ('g = (a:int64... b:int64) => a', ''), ('', 'printl(xs[$clamp 1..2 3])'),
    ('', 'printl(xs[$clip 1..])'), ('', 'printl(1 in? (..2])'), ('', 'printl([1 2; 3 4])'),
    ('', 'printl([1 2 ; 3])'), ('', 'let r = [x=1 2]'), ('', 'let d = [loop x in xs x -> 1 2]'),
    ('', 'printl(xs[new .. 2])'), ('', '[a a] = [1 2]'), ('', 'let [p as q  q] = [1 2]'),
    ('', 'printl(1 ??<A B> 2)'), ('', 'printl(0x"zz")'), ('', 'printl(members(<1 | 2>, 3))')])
def test_migrated_forms_diagnostics(compiler, tmp_path, top, body):
    source = tmp_path / 'migrated.dewy'
    source.write_text(f'{top}\nf0 = ():>void => {{}}\nmain=():>void=>{{\nlet xs = [1]\n{body}\n}}\n')
    results = []
    for mode in ('old', 'direct', 'compare'):
        result = subprocess.run([compiler, 'check', source],
                                env=dict(os.environ, DEWY_FRONTEND=mode),
                                capture_output=True, text=True, timeout=30)
        results.append((result.returncode, result.stdout, result.stderr))
    assert results[0] == results[1] == results[2]
