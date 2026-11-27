"""Behavior tests for compiler/x64_baseline.dewy (direct default-mode x86-64 emitter)."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


PROGRAM = '''
$runtime_checks

Pair:type=[a:int64 b:string]
Tag:type=[code:int64]
Label:type=[text:string]
Shape:type=Tag | Label

make_pair=(n:int64 s:string):>Pair=>{
    let text="v={n}:{s}"
    Pair[n text]
}

pick_label=(s:Shape fallback:string):>string=>{
    if s is? Label {return s.text}
    fallback
}

opt_demo=(x:int64 | none y:string | none):>string=>{
    let a=x ?? -1
    let b=y ?? "empty"
    let c=if y is? string {y} else {"none"}
    "{a}/{b}/{c}"
}

arr_demo=(n:int64):>string=>{
    let xs:array<int64>=[1 2 3]
    xs.push(n)
    let sub=xs[1..3)
    let zeros:array<int64>=fill(0 4)
    let words:array<string>=["alpha" "beta" "gamma"]
    let wsub=words[1..3)
    let out="{xs.length}:{sub.length}:{sub[0]}:{sub[1]}:{zeros.length}:{wsub.length}:{wsub[0]}:{wsub[1]}"
    xs.clear()
    "{out}:{xs.length}"
}

slice_str=(s:string):>string=>{
    let head=s[0..4)
    let tail=s[5..9)
    "{head}-{tail}"
}

main=():>void=>{
    let p=make_pair(7 "ok")
    let s1:Shape=Tag[42]
    let s2:Shape=Label["hi"]
    printl"{p.a} {p.b}"
    printl"{pick_label(s1 "fb")} {pick_label(s2 "fb")}"
    printl"{opt_demo(none none)}"
    printl"{opt_demo(9 "yes")}"
    printl"{arr_demo(99)}"
    printl"{slice_str("dewy_lang")}"
}
'''


def test_x64_baseline_default_matches_release(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_probe.dewy'
    source.write_text(PROGRAM)
    outputs = []
    for tag, flags in (('default', []), ('release', ['--release'])):
        binary = tmp_path / f'probe_{tag}'
        built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0] == (
        '7 v=7:ok\n'
        'fb hi\n'
        '-1/empty/none\n'
        '9/yes/yes\n'
        '4:2:2:3:4:2:beta:gamma:0\n'
        'dewy-lang\n'
    )


def test_x64_baseline_ships_dewy(compiler):  # noqa: F811
    binary = compiler.read_bytes()
    assert b'/compiler/x64_baseline.dewy\0' in binary
    assert b'/compiler/x64_baseline.jo\0' not in binary
