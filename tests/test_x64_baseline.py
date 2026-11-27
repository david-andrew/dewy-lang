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


ROUND2_PROGRAM = '''
$runtime_checks

BoxedRec:type = [k:int64 v:string]
SmallTag:type = 'a' | 'b'
WideTag:type = 'a' | 'b' | 'c'
SubU:type = int64 | string
SuperU:type = int64 | string | bool

let g_init_val:int64 = 100 + 23

float_and_exact = (a:int64 b:float64 u:uint64):>string => {
    let f:float64 = b + float64(a * 3) + float64(a * 4)
    let f32v:float32 = float32(f) + float32(1.5)
    let back:float64 = float64(f32v) - 0.5
    let uf:float64 = float64(u)
    let root:float64 = sqrt(abs(back))
    let zs:array<float64> = fill(0.0 3)
    let nanv:float64 = 0.0 / 0.0
    let nan_eq:bool = nanv =? nanv
    let nan_ne:bool = nanv not=? nanv
    let nan_lt:bool = nanv <? 1.0
    let n32:int32 = int32(a + 7)
    let n8:uint8 = uint8(a + 2)
    let csum:int64 = int64(n32) + int64(n8) + int64(back)
    let acc:float64 = 1.0
    acc += 2.5
    acc -= 0.5
    acc *= 2.0
    acc /= 3.0
    "{csum}:{zs.length}:{nan_eq}:{nan_ne}:{nan_lt}:{int64(root)}:{int64(uf / 1048576.0)}:{int64(acc * 10.0)}"
}

fixed_and_ops = (idx:int64):>string => {
    let fx:array<int64 length=4> = [10 20 30 40]
    fx[idx] = fx[idx] + 5
    let rep:array<int64 length=3> = fill(int64(7) 3)
    let sl = fx[1..3)
    let fsum:int64 = 0
    loop v in fx { fsum += v }
    let sfx:array<string length=2> = ["hi" "yo"]
    let tup:[int64 string] = [fx.length sfx[1]]
    let r1 = BoxedRec[1 "x"]
    let r2 = BoxedRec[1 "x"]
    let r3 = BoxedRec[2 "x"]
    let xs:array<int64> = [1 2 3]
    xs.reserve(8)
    xs.extend([4 5])
    let popped = xs.pop()
    xs.truncate(3)
    xs.resize(5)
    let st:SmallTag = 'b'
    let wt:WideTag = st
    let wtxt:string = wt as string
    let su:SubU = "ok"
    let wu:SuperU = su
    let wu_s:string = if wu is? string {wu} else {"no"}
    "{fsum}:{rep[2]}:{sl[0]}:{sl[1]}:{tup[0]}:{tup[1]}:{r1 =? r2}:{r1 not=? r3}:{popped}:{xs.length}:{wtxt}:{wu_s}"
}

math_int_demo = (n:int):>string => {
    let big:int = 5000000000000000000
    let huge:int = big * big + n
    let back:int = (huge - n) // big
    let rem:int = (huge + 7) % 10
    let neg:int = -n
    let inv:int = ~n
    let sh:int = (int(1) << 70) >> 68
    let acc:int = 0
    loop i in [0..5) {
        acc += i * 2
    }
    let big_lo:int = big + 0
    let big_hi:int = big + 3
    let bcnt:int = 0
    loop k in [big_lo..big_hi) {
        if k >=? big_lo { bcnt += 1 }
    }
    let mres:string = match n {
        <0> => "zero"
        _x:int<1 <=? _x and _x <=? 10> => "small"
        _ => "other"
    }
    let xs:array<int> = [n big huge]
    let popped:int = xs.pop()
    let f:float64 = float64(n) + float64(int(float64(3.9)))
    let w:int64<overflow='wrap'> = int64<overflow='wrap'>(huge)
    let u32v:uint32 = uint32(acc)
    let labels:array<string> = [loop i in [0..3) "k{i}"]
    "{back}:{rem}:{neg}:{inv}:{sh}:{acc}:{bcnt}:{mres}:{popped =? huge}:{int64(f)}:{u32v}:{w =? int64<overflow='wrap'>(huge)}:{labels.join(",")}"
}

main = ():>void => {
    let big_u:uint64 = uint64(9223372036854775808)
    printl"{g_init_val}"
    printl"{float_and_exact(5 2.5 big_u)}"
    printl"{fixed_and_ops(2)}"
    printl"{math_int_demo(6)}"
    printl"{math_int_demo(0)}"
}
'''


def test_x64_baseline_round2_matches_release(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_r2.dewy'
    source.write_text(ROUND2_PROGRAM)
    outputs = []
    for tag, flags in (('default', []), ('release', ['--release'])):
        binary = tmp_path / f'r2_{tag}'
        built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].splitlines()[0] == '123'
    assert outputs[0].splitlines()[2] == '105:7:20:35:4:yo:true:true:5:5:b:ok'
    assert outputs[0].splitlines()[3] == '5000000000000000000:3:-6:-7:4:20:3:small:true:9:20:true:k0,k1,k2'


def test_x64_baseline_exact_overflow_traps(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_ovf.dewy'
    source.write_text('''
$runtime_checks
boom = (x:int32 y:int32):>int32 => {
    let extra:int64 = 0
    loop i in [0..4) { extra += i }
    let z:int32 = x + y
    if extra <? 0 { return 0 }
    z
}
main = ():>void => {
    printl"{boom(2000000000 1000000000)}"
}
''')
    binary = tmp_path / 'ovf_default'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0


ROUND3_PROGRAM = '''
$runtime_checks

Limb:type = array<int64<x => x >=? -0x20000 and x <=? 0x1ffff> length=4>

tag_text = (n:int64):>string => "t{n}"

masked_swap = (@a:Limb @b:Limb bit:int64<i => i >=? 0 and i <=? 1>):>void => {
    let m = -bit
    let inv = ~m
    loop i in [0..4) {
        let t = (m and (a[i] xor b[i])) or (inv and 0)
        a[i] = a[i] xor t
        b[i] = b[i] xor t
    }
}

round3_features = (x:float64 y:float32 n:int64):>string => {
    let dbits:uint64 = $unsafe (x transmute uint64)
    let dback:float64 = $unsafe (dbits transmute float64)
    let fbits:uint32 = $unsafe (y transmute uint32)
    let fback:float32 = $unsafe (fbits transmute float32)
    let small:int = -n
    let small_inv:int = ~small
    let wrap_small:int64<overflow='wrap'> = int64<overflow='wrap'>(small)
    let big:int = int(1) << 70
    let wrap_big:int64<overflow='wrap'> = int64<overflow='wrap'>(big + 42)
    let dyn:array<int64> = [10 20 30]
    let fx:array<int64 length=3> = dyn
    let back_dyn:array<int64> = fx
    let sfx:array<string length=2> = ["aa" "bb"]
    let sback:array<string> = sfx
    let removed_i:int64 = back_dyn.pop(1)
    let removed_s:string = sback.pop(0)
    let m_int:dict<string int64> = ["k1" -> 11 "k2" -> 22]
    let m_flt:dict<string float64> = ["pi" -> 3.5 "e" -> 2.5]
    let m_str:dict<string string> = ["hi" -> "there"]
    let m_empty:dict<string int64> = []
    let p:Limb = [1 2 3 4]
    let q:Limb = [10 20 30 40]
    masked_swap(@p @q 1)
    let parts:array<string> = []
    loop i in [0..3) {
        let idx:int64 = i * 2 + 1
        let a1 = tag_text(idx)
        let a2 = tag_text(idx + 1)
        let a3 = tag_text(idx + 2)
        let a4 = tag_text(idx + 3)
        let a5 = tag_text(idx + 4)
        if i =? 1 { parts.push("{a1}:{a2}:{a3}:{a4}:{a5}") }
    }
    let f_out:string = "{int64(dback * 10.0)}:{int64(float64(fback) * 10.0)}:{dbits}:{fbits}"
    let m_out:string = "{m_int["k1"]}:{m_int["k2"]}:{int64(m_flt["pi"] * 10.0)}:{m_str["hi"]}:{m_empty.length}"
    "{f_out}|{small}:{small_inv}:{wrap_small}:{wrap_big}|{removed_i}:{back_dyn.length}:{removed_s}:{sback.length}|{m_out}|{p[0]}:{q[0]}|{parts.join(",")}"
}

main = ():>void => {
    printl"{round3_features(1.5 float32(2.5) 7)}"
}
'''


def test_x64_baseline_round3_matches_release(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_r3.dewy'
    source.write_text(ROUND3_PROGRAM)
    outputs = []
    for tag, flags in (('default', []), ('release', ['--release'])):
        binary = tmp_path / f'r3_{tag}'
        built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0] == (
        '15:25:4609434218613702656:1075838976|-7:6:-7:42|20:2:aa:1|11:22:35:there:0|10:1|t3:t4:t5:t6:t7\n'
    )


def test_x64_baseline_arr2fixed_length_mismatch_traps(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_arr2fixed_trap.dewy'
    source.write_text('''
$runtime_checks
bad = (xs:array<int64>):>int64 => {
    let fx:array<int64 length=3> = xs
    fx[0] + fx[1] + fx[2]
}
main = ():>void => {
    let xs:array<int64> = [1 2]
    printl"{bad(xs)}"
}
''')
    binary = tmp_path / 'arr2fixed_trap'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0


ROUND4_PROGRAM = '''
$runtime_checks

round4_features = (n:int64):>string => {
    let a:array<uint8 length=4> = [1 2 3 4]
    let b:array<uint8 length=4> = [1 2 3 4]
    let c:array<uint8 length=4> = [1 2 9 4]
    let d1:array<int64> = [10 20 30]
    let d2:array<int64> = [10 20 30]
    let d3:array<int64> = [10 20 31]
    let up_excl:int64 = 0
    loop i in [0, 2..10) { up_excl += i }
    let up_incl:int64 = 0
    loop i in [1, 4..10] { up_incl += i }
    let dn_excl:int64 = 0
    loop i in [10, 7..1) { dn_excl += i }
    let dn_incl:int64 = 0
    loop i in [10, 7..1] { dn_incl += i }
    let empty_up:int64 = 0
    loop i in [10, 12..5] { empty_up += 1 }
    let empty_dn:int64 = 0
    loop i in [2, 0..5] { empty_dn += 1 }
    let dyn_sum:int64 = 0
    loop i in [n, n + 3..n + 10] { dyn_sum += i }
    let pushed:array<int64> = []
    loop i in [0..6) { pushed.push(i * 3) }
    "{a =? b}:{a not=? c}:{d1 =? d2}:{d1 not=? d3}|{up_excl}:{up_incl}:{dn_excl}:{dn_incl}:{empty_up}:{empty_dn}:{dyn_sum}|{pushed.length}:{pushed[5]}"
}

main = ():>void => {
    printl"{round4_features(2)}"
}
'''


def test_x64_baseline_round4_matches_release(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_r4.dewy'
    source.write_text(ROUND4_PROGRAM)
    outputs = []
    for tag, flags in (('default', []), ('release', ['--release'])):
        binary = tmp_path / f'r4_{tag}'
        built = subprocess.run([compiler, 'build', source, *flags, '-o', binary],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0] == 'true:true:true:true|20:22:21:22:0:0:26|6:15\n'


def test_x64_baseline_step_zero_traps(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'baseline_step0.dewy'
    source.write_text('''
$runtime_checks
step0 = (x:int64):>int64 => {
    let acc:int64 = 0
    loop i in [x, x..x + 5] { acc += i }
    acc
}
main = ():>void => {
    printl"{step0(3)}"
}
''')
    binary = tmp_path / 'step0_default'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0




