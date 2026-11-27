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


CONTROL_FLOW_PROGRAM = '''
$runtime_checks

Color:type = 'red' | 'green' | 'blue'
Val:type = int64 | string

classify_dense = (code:int64):>int64 => match code {
    <0> => 17
    <1> => 4
    <2> => 91
    <3> => 6
    <4> => 22
    <5> => 37
    <6> => 8
    _ => 5
}

match_multi = (code:int64 s:string v:Val o:int64?):>string => {
    let tag:int64 = match code {
        <0> => 10
        <1> => 20
        <2> => 30
        <3> => 40
        <4> => 50
        _ => 99
    }
    let rng:string = match code {
        _x:int64<0 <=? _x and _x <=? 2> => "lo"
        _x:int64<3 <=? _x and _x <? 5> => "mid"
        _ => "hi"
    }
    let sm:int64 = match s {
        <"alpha"> => 1
        <"beta"> => 2
        _ => 0
    }
    let vm:string = match v {
        n:int64 => "i:{n}"
        t:string => "s:{t}"
    }
    let om:int64 = match o {
        <none> => -1
        n:int64 => n + 1
    }
    "{tag}:{rng}:{sm}:{vm}:{om}"
}

enum_match = (c:Color):>int64 => {
    let extra:int64 = 100
    let v:int64 = match c {
        <'red'> => 10
        <'green'> => 20
        <'blue'> => 30
    }
    extra + v
}

defer_and_loops = (limit:int64):>string => {
    let log:array<string> = []
    defer log.push("fn-end")
    let sum:int64 = 0
    let xs:array<int64> = [10 20 30 40]
    let ys:array<int64> = [10 20 99 40]
    let n:int64 = xs.length
    let diff:int64 = 0
    loop i in [0..n) {
        if xs[i] not=? ys[i] { diff += 1 }
        if i % 2 =? 0 { sum += xs[i] }
    }
    let incl:int64 = 0
    loop k in [1..4] { incl += k }
    let elem_sum:int64 = 0
    loop x in xs { elem_sum += x }
    let byte_sum:int64 = 0
    loop b in ("abc" as array<uint8>) { byte_sum += b as int64 }
    let d:dict<string int64> = []
    d["a"] = 3
    d["b"] = 5
    let dsum:int64 = 0
    loop [k v] in d { dsum += v + (k.length as int64) }
    let wsum:int64 = 0
    let wi:int64 = 0
    loop wi <? limit {
        defer log.push("w{wi}")
        wi += 1
        if wi =? 2 { continue }
        wsum += wi
        if wi =? 4 { break }
    }
    let opts:array<int64?> = [3 4 none 9]
    let oi:int64 = 0
    let osum:int64 = 0
    loop oi <? opts.length {
        let ov = opts[oi]
        if ov is? int64 {
            osum += ov
        } else {
            break
        }
        oi += 1
    }
    let lsum:int64 = 0
    $outer loop a in [0..3) {
        defer log.push("o{a}")
        loop b in [0..4) {
            if b =? 2 { continue $outer }
            if a =? 2 and b =? 1 { break $outer }
            lsum += a * 10 + b
        }
    }
    "{sum}:{diff}:{incl}:{elem_sum}:{byte_sum}:{dsum}:{wsum}:{osum}:{lsum}:{log.join(",")}"
}

defer_return_val = (x:int64):>int64 => {
    let acc:int64 = x
    defer { acc += 100 }
    if x >? 0 {
        defer { acc += 10 }
        return acc + 5
    }
    return acc + 1
}

main = ():>void => {
    printl"{classify_dense(0)} {classify_dense(5)} {classify_dense(99)}"
    printl"{match_multi(2 "beta" 42 7)}"
    printl"{match_multi(4 "x" "hi" none)}"
    printl"{match_multi(9 "alpha" 1 8)}"
    printl"{enum_match('red')} {enum_match('blue')}"
    printl"{defer_and_loops(6)}"
    printl"{defer_return_val(7)} {defer_return_val(0)}"
}
'''


def test_x64_baseline_control_flow_matches_release(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_cf.dewy'
    source.write_text(CONTROL_FLOW_PROGRAM)
    outputs = []
    for tag, flags in (('default', []), ('release', ['--release'])):
        binary = tmp_path / f'cf_{tag}'
        built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0] == (
        '17 37 5\n'
        '30:lo:2:i:42:8\n'
        '50:mid:0:s:hi:-1\n'
        '99:hi:1:i:1:9\n'
        '110 130\n'
        '40:1:10:100:294:10:8:7:42:w1,w2,w3,w4,o0,o1,o2\n'
        '12 1\n'
    )

