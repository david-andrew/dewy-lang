"""Fixed-width storage narrows exact, allocation-free intermediates."""
import subprocess

import pytest

from tests.support import compiler


def build(compiler, tmp_path, body, release=False):
    source = tmp_path / 'exact.dewy'
    source.write_text(body)
    binary = tmp_path / 'exact'
    result = subprocess.run([compiler, 'build', source, '-o', binary] +
                            (['--release'] if release else []), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return binary


@pytest.mark.parametrize('release', [False, True])
def test_exact_intermediates(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
ratio=(a:int32 b:int32 c:int32):>int32=>(a*b)//c
wide=(a:int64 b:int64 c:int64):>int64=>(a*b)//c
sum=(a:int32 b:int32):>int64=>a+b
cancel=(a:int64 b:int64):>int64=>(a+b)-b
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    let c=int64(to_int(args[3]) ?? 1)
    printl(wide(a b c))
    printl(cancel(a b))
    printl(sum(2147483647 2147483647))
    printl(ratio(2000000000 2000000000 2000000000))
}
''', release)
    for a, b, c in [(2**62, 3, 3), (-2**63, -1, 2), (2**62, -3, 3), (-7, 3, 2)]:
        ran = subprocess.run([binary, str(a), str(b), str(c)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.splitlines() == [str(a*b//c), str(a), '4294967294', '2000000000']


@pytest.mark.parametrize('release', [False, True])
def test_exact_store_check(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
add=(a:int8 b:int8):>int8=>a+b
main=(args:array<string>)=>{
    let a=int8(to_int(args[1]) ?? 0)
    printl(add(a 1))
}
''', release)
    ran = subprocess.run([binary, '126'], capture_output=True, text=True)
    assert ran.returncode == 0 and ran.stdout.strip() == '127', ran.stderr
    ran = subprocess.run([binary, '127'], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout


def test_exact_unbounded_shift_rejected(compiler, tmp_path):
    source = tmp_path / 'unbounded.dewy'
    source.write_text('f=(a:int64 n:int64):>int64=>(a << n) >> n\nmain=()=>printl(f(1 3))\n')
    result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'width' in result.stderr and 'guard' in result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_exact_guards_and_conversions(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
shift=(a:int64 n:int64):>int64=>{
    if n <? 0 or n >=? 64 return 0
    return (a << n) >> n
}
difference=(a:uint64 b:uint64):>int64=>int64(a-b)
wrapped=(a:int64 b:int64):>uint8=>uint8<overflow='wrap'>(a*b)
saturated=(a:int64 b:int64):>int8=>int8<overflow='saturate'>(a*b)
mathematical=(a:int64 b:int64):>int=>int(a*b)
main=()=>{
    printl(shift(-9223372036854775808 63))
    printl(shift(9223372036854775807 63))
    printl(difference(1 2))
    printl(wrapped(9223372036854775807 3))
    printl(saturated(-9223372036854775808 -1))
    printl(mathematical(9223372036854775807 9223372036854775807))
}
''', release)
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(-2**63), str(2**63-1), '-1', '253', '127', str((2**63-1)**2)]


@pytest.mark.parametrize('release', [False, True])
def test_exact_storage_boundaries(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, '''
Box:type=[value:int8]
main=(args:array<string>)=>{
    let a=int8(to_int(args[1]) ?? 0)
    let b=Box[0]
    let xs:array<int8>=[0]
    b.value=a+1
    xs[0]=b.value+1
    xs[0]+=1
    printl(xs[0])
}
''', release)
    ok = subprocess.run([binary, '124'], capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.strip() == '127', ok.stderr
    for a in (125, 126, 127):
        bad = subprocess.run([binary, str(a)], capture_output=True, text=True)
        assert bad.returncode != 0 and not bad.stdout


def test_exact_comptime_and_bounded_power(compiler, tmp_path):
    binary = build(compiler, tmp_path, '''
power=(a:int64 n:int64):>int64=>{
    if n <? 0 or n >? 4 return 0
    return (a^n)//(a^n)
}
absolute=(a:int64):>int=>int(abs(a))
ratio=(a:int64 b:int64):>int64=>(a*b)//b
const RESULT=ratio(9223372036854775807 3)
$assert RESULT =? int64.max
main=()=>{
    printl(power(9223372036854775807 4))
    printl(absolute(-9223372036854775808))
    printl(RESULT)
}
''')
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['1', str(2**63), str(2**63-1)]


def test_exact_store_policy_diagnostics(compiler, tmp_path):
    for directive in ('$runtime_checks=false', '$no_hidden_costs'):
        source = tmp_path / 'strict.dewy'
        source.write_text(directive + '\nf=(a:int64):>int64=>a+1\nmain=()=>{f(0);}\n')
        result = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
        assert result.returncode != 0
        assert 'fits int64' in result.stderr and 'guard' in result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_exact_comparison_with_mathematical_counter(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(size:int64):>int=>{
    let at=6
    loop at <=? size-64 at+=64
    return at
}
main=()=>printl(f(184))
""", release)
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '134'


@pytest.mark.parametrize('release', [False, True])
def test_exact_float_conversion(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(a:int64 b:int64):>float64=>float64(a*b)
g=(a:int64 b:int64):>float32=>float32(a*b)
main=(args:array<string>)=>{
 let a=int64(to_int(args[1]) ?? 0)
 let b=int64(to_int(args[2]) ?? 0)
 printl(f(a b) =? float64(int(a)*int(b)))
 printl(g(a b) =? float32(int(a)*int(b)))
}
""", release)
    for a, b in [(2**63-1, 2**63-1), (-2**63, 2**63-1), (2**62+129, 1025), (0, -2**63), (2**62+127, 513)]:
        result = subprocess.run([binary, str(a), str(b)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ['true', 'true']


def test_exact_match_and_unsigned_comparison(compiler, tmp_path):
    binary = build(compiler, tmp_path, """
f=(a:int64):>int64=>match -a {<3>=>-2 _=>0}
g=(u:uint64):>bool=>((u and 12)-(u-u)) =? 0
main=()=>{
 printl(f(int64.min))
 printl(g(0))
 printl(g(4))
 let u:uint64=0
 $runtime_assert ((u and 12)-(u-u)) =? 0
}
""")
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['0', 'true', 'false']


@pytest.mark.parametrize('release', [False, True])
def test_exact_explicit_conversion_is_boundary(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(a:int8):>int64=>int64(int8(a+1))-1
main=(args:array<string>)=>printl(f(int8(to_int(args[1]) ?? 0)))
""", release)
    good = subprocess.run([binary, '126'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '126', good.stderr
    bad = subprocess.run([binary, '127'], capture_output=True, text=True)
    assert bad.returncode == 101 and not bad.stdout, bad.stderr


def test_exact_width_independent_of_shift_count(compiler, tmp_path):
    binary = build(compiler, tmp_path, """
f=(n:int64):>int64=>(int64(0) << n)+(int64(1)^n)+(int64(-1)^n)
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0)))
""")
    for n, value in [(10000000, 2), (10000001, 0)]:
        result = subprocess.run([binary, str(n)], capture_output=True, text=True)
        assert result.returncode == 0 and result.stdout.strip() == str(value), result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_exact_minimum_quotient(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(a:int64 b:int64):>int=>{if b not=? 0 return 0; return int((a+b)//(-1))}
g=(a:int64 b:int64):>int=>{if b not=? 1 return 0; return int((a*b)//(-1))}
main=()=>{printl(f(int64.min 0)); printl(g(int64.min 1))}
""", release)
    result = subprocess.run([binary], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(2**63), str(2**63)]


@pytest.mark.parametrize('release', [False, True])
def test_exact_stored_large_multiplier(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(x:int64):>int64=>x*4294967297
main=(args:array<string>)=>printl(f(int64(to_int(args[1]) ?? 0)))
""", release)
    for value in (0, 1, -1, 2147483647):
        ran = subprocess.run([binary, str(value)], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == str(value*4294967297), ran.stderr
    ran = subprocess.run([binary, '2147483648'], capture_output=True, text=True)
    assert ran.returncode != 0 and not ran.stdout


@pytest.mark.parametrize('release', [False, True])
def test_exact_power_count_representation(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(n:int):>int64=>{if n <? 0 or n >? 4 return 0; return int64(2)^n}
g=(n:uint64):>int64=>int64(1)^n
h=(n:int):>int64=>int64(-1)^n
z=(n:int):>int64=>int64(0)^n
wide=(n:int64):>int64=>(int64(1)^(n+n))+(int64(0)^(n+n))
right=(a:int64 n:uint64):>int64=>(a+a) >> (n+n)
main=()=>{
 printl(f(3))
 printl(g(uint64.max))
 printl(int64(1)^uint64.max)
 printl(h(18446744073709551616))
 printl(h(18446744073709551617))
 printl(z(18446744073709551616))
 printl(wide(int64.max))
 printl(right(100 uint64.max))
}
""", release)
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['8', '1', '1', '1', '-1', '0', '1', '0']


@pytest.mark.parametrize('release', [False, True])
def test_wide_dividend_cannot_prove_narrow_store(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
f=(a:int64 b:int64 d:int64):>int64=>{
 if a <? 0 or b <? 0 or d <? 1 or d >? 2 return 0
 return (a+b)//d
}
main=(args:array<string>)=>printl(f(int64.max 1 int64(to_int(args[1]) ?? 1)))
""", release)
    good = subprocess.run([binary, '2'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == str(2**62), good.stderr
    bad = subprocess.run([binary, '1'], capture_output=True, text=True)
    assert bad.returncode != 0 and not bad.stdout, bad.stderr


@pytest.mark.parametrize('release', [False, True])
def test_exact_index_check_precedes_assignment_rhs(compiler, tmp_path, release):
    binary = build(compiler, tmp_path, """
value=():>int64=>{printl("rhs"); return 3}
main=(args:array<string>)=>{
 let i=int64(to_int(args[1]) ?? 0)
 let xs:array<int64>=[0]
 xs[i+1]=value()
}
""", release)
    good = subprocess.run([binary, '-1'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == 'rhs', good.stderr
    bad = subprocess.run([binary, str(2**63-1)], capture_output=True, text=True)
    assert bad.returncode != 0 and not bad.stdout, bad.stderr
