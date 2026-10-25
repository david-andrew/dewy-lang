"""Finite arithmetic facts survive ordinary integer storage and conversions."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


PROVED = {
    'signed_shift': ('''f=(x:int64):>int8=>int8(x >> 56)
printl(f(-9223372036854775808) f(-1) f(0) f(9223372036854775807))''', '-128 -1 0 127\n'),
    'shift_interval': ('''f=(x:int64 by:int64):>int8=>{
 if 56 <=? by <=? 63 return int8(x >> by)
 0
}
printl(f(-9223372036854775808 56) f(-9223372036854775808 63) f(9223372036854775807 56))''', '-128 -1 127\n'),
    'negative_divisor': ('''f=(x:int64 d:int64):>int64=>{
 if d >=? -8 and d <=? -2 return x // d
 0
}
printl(f(-9223372036854775808 -2) f(9223372036854775807 -2) f(5 -3) f(-5 -3))''', '4611686018427387904 -4611686018427387904 -2 1\n'),
    'negative_modulus': ('''f=(x:int d:int):>int8=>{
 if d >=? -128 and d <? 0 return int8(x % d)
 0
}
printl(f(-1000 -128) f(1000 -128) f(999999999999999999999999 -100) f(-999999999999999999999999 -100))''', '-104 -24 -1 -99\n'),
    'wide_clamp': ('''f=(x:int64):>int8=>{
 let y:int=x*x
 int8(min(127 max(-128 y)))
}
printl(f(-9223372036854775808) f(9223372036854775807) f(2))''', '127 127 4\n'),
    'endpoint_guards': ('''f=(x:int):>int64=>{
 if x >=? -9223372036854775808 and x <=? 9223372036854775807 return x
 7
}
printl(f(-9223372036854775808) f(9223372036854775807) f(9223372036854775808) f(-9223372036854775809))''', '-9223372036854775808 9223372036854775807 7 7\n'),
    'fixed_join_roundtrip': ('''f=(x:int64 y:int64 choose:bool):>int64=>{
 let z:int=x
 if choose z=y
 z
}
printl(f(-9223372036854775808 9223372036854775807 false) f(-9223372036854775808 9223372036854775807 true))''', '-9223372036854775808 9223372036854775807\n'),
    'fixed_roundtrip': ('''f=(x:int64):>int64=>{let y:int=x return y}
printl(f(-9223372036854775808) f(9223372036854775807))''', '-9223372036854775808 9223372036854775807\n'),
    'script_literal_product': ('''let bound=5
f=():>int8=>bound*bound
printl(f())''', '25\n'),
    'masked_loop': ('''f=(xs:array<uint8>):>uint8=>{
 let x=0
 loop b in xs x=(x*3+b) and 255
 uint8(x)
}
printl(f([]) f([255 255 255]))''', '0 243\n'),
    'negative_remainder_loop': ('''f=(xs:array<uint8>):>int8=>{
 let x=0
 loop b in xs x=(x+b) % -128
 int8(x)
}
printl(f([]) f([255 255]))''', '0 -2\n'),
    'bounded_product': ('''f=(i:int k:int j:int):>int32=>{
 if 0 <=? i <? 100 and 0 <=? k <? 100 and 0 <=? j <? 100 return i*k+j
 0
}
printl(f(99 99 99))''', '9900\n'),
    'literal_loop_product': ('''let out:array<int64>=[]
loop i in [1..5] out.push(i*i)
printl(out)''', '[1 4 9 16 25]\n'),
}


@pytest.mark.parametrize('name', PROVED)
@pytest.mark.parametrize('release', [False, True])
def test_narrowing_proved(compiler, tmp_path, name, release):
    source, output = PROVED[name]
    path = tmp_path / f'{name}.dewy'
    path.write_text(source + '\n')
    binary = tmp_path / name
    built = subprocess.run([compiler, 'build', path, '-o', binary] + (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == output


REJECTED = {
    'shift_too_small': 'f=(x:int64):>int8=>int8(x >> 55)\nprintl(f(9223372036854775807))',
    'unbounded_shift': 'f=(x:int):>int8=>int8(x >> 56)\nprintl(f(9999999999999999999999999999999))',
    'wide_shift': 'f=(x:int64):>int8=>int8((x << 63) >> 56)\nprintl(f(9223372036854775807))',
    'unbounded_positive_division': 'f=(x:int):>int64=>x // 2\nprintl(f(99999999999999999999999999))',
    'unbounded_positive_modulus': 'f=(x:int d:int):>int64=>{if d >? 0 return x % d return 0}\nprintl(f(-1 99999999999999999999999999))',
    'unbounded_negative_division': 'f=(x:int):>int64=>x // -2\nprintl(f(99999999999999999999999999))',
    'unbounded_negative_modulus': 'f=(x:int d:int):>int64=>{if d <? 0 return x % d return 0}\nprintl(f(1 -99999999999999999999999999))',
    'modulus_zero': 'f=(x:int d:int):>int8=>{if -128 <=? d <=? 0 return int8(x % d) return 0}\nprintl(f(2 0))',
    'modulus_too_low': 'f=(x:int):>int8=>int8(x % -130)\nprintl(f(1))',
    'endpoint_guard_then_write': 'f=(x:int):>int64=>{if x >=? -9223372036854775808 and x <=? 9223372036854775807 {x=99999999999999999999999 return x} return 0}\nprintl(f(0))',
    'unbounded_relational_cycle': 'f=(x:int y:int):>int64=>{if x <=? y and y <=? x return x return 0}\nprintl(f(99999999999999999999999 99999999999999999999999))',
    'missing_lower_endpoint': 'f=(x:int):>int64=>{if x <=? 9223372036854775807 return x return 0}\nprintl(f(-9999999999999999999999999))',
    'missing_upper_endpoint': 'f=(x:int):>int64=>{if x >=? -9223372036854775808 return x return 0}\nprintl(f(9999999999999999999999999))',
    'unknown_roundtrip': 'f=(x:int):>int64=>x\nprintl(f(9999999999999999999999999))',
    'wide_roundtrip': 'f=(x:int64):>int64=>{let y:int=x+1 return y}\nprintl(f(9223372036854775807))',
    'script_literal_replaced': 'let bound=5\nchange=()=>{bound=1000}\nf=():>int8=>bound*bound\nchange()\nprintl(f())',
    'script_literal_exposed': 'change=(@n:int)=>{n=1000}\nlet bound=5\nf=():>int8=>bound*bound\nchange(@bound)\nprintl(f())',
    'mask_loop_bad_entry': 'f=(xs:array<uint8>):>uint8=>{let x=256 loop b in xs x=(x+b) and 255 return uint8(x)}\nprintl(f([]))',
    'mask_loop_other_write': 'f=(xs:array<uint8>):>uint8=>{let x=0 loop b in xs {x=(x+b) and 255 if b =? 1 x=256} return uint8(x)}\nprintl(f([1]))',
    'product_too_large': 'f=(x:int y:int):>int8=>{if 0 <=? x <? 100 and 0 <=? y <? 100 return x*y return 0}\nprintl(f(99 99))',
}


@pytest.mark.parametrize('name', REJECTED)
def test_narrowing_still_required(compiler, tmp_path, name):
    path = tmp_path / f'{name}.dewy'
    path.write_text(REJECTED[name] + '\n')
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True)
    assert checked.returncode != 0, checked.stdout + checked.stderr
    assert 'cannot prove' in checked.stderr or 'does not fit' in checked.stderr, checked.stderr


def test_obligations_demands_exact_store_inputs(compiler, tmp_path):
    path = tmp_path / 'demand.dewy'
    path.write_text('$runtime_checks\nf=(x:int64):>int64=>{if 0 <=? x <? 100 return x+1 return 0}\nprintl(f(10))\n')
    checked = subprocess.run([compiler, 'check', '--obligations', path], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert 'exact integer result fits' not in checked.stdout, checked.stdout
