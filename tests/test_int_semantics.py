"""Mathematical int identity and checked fixed-width boundaries."""
import shutil
import subprocess

import pytest

from tests.test_core import Scripts, compiler


MIN = -(1 << 63)
MAX = (1 << 63) - 1
SOURCE = '''const WORD_MAX=uint64.max
big_echo=(n:bigint):>bigint=>n
kind=(x:int):>string=>"int"
kind=(x:int64):>string=>"int64"
identity=<T>(x:T):>T=>x
main=(argv:array<string>)=>{
    let op=argv[1]
    let x=int(to_int(argv[2]) ?? 0)
    let y=int(to_int(argv[3]) ?? 0)
    if op=?"add" {printl"{x+y}" return}
    if op=?"sub" {printl"{x-y}" return}
    if op=?"mul" {printl"{x*y}" return}
    if op=?"neg" {printl"{-x}" return}
    if op=?"abs" {printl"{abs(x)}" return}
    if op=?"pow" {printl"{x^y}" return}
    if op=?"pow-call" {printl"{pow(x y)}" return}
    if op=?"shl" {printl"{x<<y}" return}
    if op=?"u-shr" {printl"{x>>uint64<overflow='wrap'>(int64(y))}" return}
    if op=?"u-shl" {printl"{x<<uint64<overflow='wrap'>(int64(y))}" return}
    if op=?"shr" {printl"{x>>y}" return}
    if op=?"div" {printl"{x//y}" return}
    if op=?"mod" {printl"{x%y}" return}
    if op=?"rational" {printl"{x/y}" return}
    if op=?"i16" {printl"{int16(x)}" return}
    if op=?"u16" {printl"{uint16(x)}" return}
    if op=?"i32" {printl"{int32(x)}" return}
    if op=?"u32" {printl"{uint32(x)}" return}
    if op=?"zero-huge-shift" {printl"{int(0)<<uint64.max}" return}
    if op=?"fixed-constants" {let v=int64<overflow='wrap'>(9223372036854775807+1) let u:uint64<overflow='wrap'>=WORD_MAX u+=1 printl"{v} {u}" return}
    if op=?"i8" {let v:int8=x printl"{v}" return}
    if op=?"u8" {printl"{x as uint8}" return}
    if op=?"u64" {printl"{uint64(x)}" return}
    if op=?"from-u64" {let v=uint64(int64(x)) printl"{int(v)}" return}
    if op=?"float" {printl"{int(to_float(argv[2]) ?? 0.0)}" return}
    if op=?"discard" {x+y; printl"done" return}
    if op=?"mutated-index" {loop i in [0..2) {i=x printl"{i+y}"} return}
    if op=?"bounded-index" {let total=0 loop i in [0..100) {total+=i+2} printl"{total}" return}
    if op=?"parse" {printl"{to_int(argv[2])}" return}
    if op=?"bigint-context" {printl"{big_echo(18446744073709551616)}" return}
    if op=?"bigint-word" {printl"{bigint(18446744073709551615)}" return}
    if op=?"bigint" {let n:bigint=18446744073709551616 printl"{n}" return}
    if op=?"float-nan" {let f=float64(x) printl"{int(f/f)}" return}
    if op=?"compound" {let v=x v+=y printl"{v}" return}
    if op=?"fixed-div" {printl"{int64<overflow='wrap'>(x)//int64<overflow='wrap'>(y)}" return}
    if op=?"fixed-narrow-pow" {printl"{int32<overflow='wrap'>(x)^int32(y)}" return}
    if op=?"fixed-narrow-floor" {printl"{kind(int32(x)//int32(y))}" return}
    if op=?"fixed-pow" {printl"{int64<overflow='wrap'>(x)^int64(y)}" return}
    if op=?"narrow-wrap" {let v:int8<overflow='wrap'>=127 v+=1 printl"{v}" return}
    if op=?"wrap" {let v=int64<overflow='wrap'>(x) v+=int64(y) printl"{v}" return}
    if op=?"identity" {
        let a=1 let xs=[1 2] let fixed:int64=1
        printl"{kind(a)} {kind(xs[0])} {kind(identity(a))} {kind(fixed)}"
        printl"{kind(x+fixed)} {kind(fixed+x)} {kind(min(x y))}"
        return
    }
    if op=?"format" {printl"{x} {string(x)}" return}
    if op=?"indices" {let xs=[10 20 30] let ix=[0 2] printl"{xs[ix]}" xs[ix] .+= [1 2] printl"{xs}" return}
    if op=?"fixed-u-div" {let v:uint64=uint64.max v//=2 printl"{v}" return}
    if op=?"index" {let xs=[10 20 30] printl"{xs[x]} {xs.length}" return}
    panic("unknown operation")
}
'''


@pytest.fixture(scope='module', params=[('native', False), ('native', True), ('wasm', False), ('wasm', True), ('arm', False), ('arm', True)],
                ids=['native-default', 'native-release', 'web-default', 'web-release', 'arm-default', 'arm-release'])
def int_program(compiler, tmp_path_factory, request):
    target, release = request.param
    directory = tmp_path_factory.mktemp('int-semantics')
    source = directory / 'integers.dewy'
    source.write_text(SOURCE)
    binary = directory / 'integers'
    flags = ['--release'] if release else []
    if target == 'arm':
        qemu = shutil.which('qemu-aarch64')
        if not qemu:
            pytest.skip('qemu-aarch64 is needed for ARM execution')
        flags += ['--target', 'aarch64-linux']
    if target == 'wasm':
        flags += ['--target', 'wasm32']
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    if target == 'native':
        return [binary]
    if target == 'arm':
        return [qemu, binary]
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed to run the web target')
    scripts = Scripts()
    scripts.feed(binary.with_suffix('.html').read_text())
    runner = directory / 'integers.cjs'
    runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(scripts.parts))
    return [node, runner]


def run(program, op, x, y=0):
    return subprocess.run([*program, op, str(x), str(y)], capture_output=True, text=True, timeout=10)


@pytest.mark.parametrize('op,x,y,expected', [
    pytest.param('add', MAX-1, 1, MAX, marks=pytest.mark.core_quick), ('add', MIN, 0, MIN), ('sub', MIN+1, 1, MIN),
    ('mul', MIN//2, 2, MIN), ('mul', MAX, 1, MAX), ('mul', MIN, 0, 0),
    ('neg', MAX, 0, -MAX), ('abs', -MAX, 0, MAX),
    ('pow', -2, 63, MIN), ('pow', 0, 0, 1), ('pow-call', 2, 62, 1 << 62),
    ('shl', -1, 63, MIN), ('shl', 0, 64, 0), ('shl', 0, MAX, 0),
    ('u-shr', -1, -1, -1), ('u-shr', 1, -1, 0), ('u-shl', 0, -1, 0),
    ('shr', MIN, 64, -1), ('shr', MAX, 64, 0), ('shr', -7, 1, -4),
    ('div', MIN, 1, MIN), ('div', -7, 3, -3), ('div', 7, -3, -3),
    ('mod', MIN, -1, 0), ('mod', -7, 3, 2), ('mod', 7, -3, -2),
    ('rational', 7, 2, '7/2'),
    ('i8', -128, 0, -128), ('i8', 127, 0, 127), ('u8', 255, 0, 255),
    ('i16', -32768, 0, -32768), ('u16', 65535, 0, 65535),
    ('i32', -(1 << 31), 0, -(1 << 31)), ('u32', (1 << 32)-1, 0, (1 << 32)-1),
    ('fixed-constants', 0, 0, f'{MIN} 0'), ('zero-huge-shift', 0, 0, 0),
    ('u64', MAX, 0, MAX), ('from-u64', MAX, 0, MAX),
    ('float', '-9223372036854775808', 0, MIN), ('float', '42.9', 0, 42),
    ('bounded-index', 0, 0, 5150), ('parse', '9223372036854775808', 0, '9223372036854775808'),
    ('parse', str(MIN), 0, str(MIN)), ('parse', 'invalid', 0, 'NotAnInteger'),
    ('bigint-context', 0, 0, '18446744073709551616'),
    ('bigint', 0, 0, '18446744073709551616'), ('bigint-word', 0, 0, '18446744073709551615'),
    ('fixed-narrow-pow', 2, 63, 0), ('fixed-narrow-floor', 7, 2, 'int64'),
    ('fixed-div', MIN, -1, MIN), ('fixed-pow', 2, 63, MIN), ('narrow-wrap', 0, 0, -128),
    ('compound', MAX-1, 1, MAX), ('wrap', MAX, 1, MIN),
    pytest.param('identity', 1, 2, 'int int int int64\nint int int', marks=pytest.mark.core_quick),
    ('format', MIN, 0, f'{MIN} {MIN}'),
    ('indices', 0, 0, '[10 30]\n[11 20 32]'), ('fixed-u-div', 0, 0, MAX),
    ('index', 2, 0, '30 3'),
])
def test_int_values(int_program, op, x, y, expected):
    result = run(int_program, op, x, y)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(expected), result.stderr


@pytest.mark.parametrize('op,x,y', [
    ('shl', 1, -1), ('shr', 1, -1),
    pytest.param('i8', 128, 0, marks=pytest.mark.core_quick), ('i8', -129, 0),
    ('i16', -32769, 0), ('i16', 32768, 0), ('u16', -1, 0), ('u16', 65536, 0),
    ('i32', -(1 << 31)-1, 0), ('i32', 1 << 31, 0), ('u32', -1, 0), ('u32', 1 << 32, 0),
    ('u8', -1, 0), ('u8', 256, 0), ('u64', -1, 0), ('float-nan', 0, 0),
])
def test_int_overflow(int_program, op, x, y):
    result = run(int_program, op, x, y)
    assert result.returncode != 0, result.stdout
    expected = 'nan does not convert to int' if op == 'float-nan' else 'integer overflow'
    assert expected in result.stdout + result.stderr


@pytest.mark.parametrize('expression', ['uint8(int(256))'])
@pytest.mark.parametrize('release', [False, True])
def test_int_constant_errors(compiler, tmp_path, expression, release):
    source = tmp_path / 'constant.dewy'
    source.write_text(f'main=()=>{{let x={expression} printl"{{x}}"}}\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'constant',
                            *(['--release'] if release else [])],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode != 0, expression
    assert any(message in built.stderr for message in ('integer overflow', 'does not fit in int')), built.stderr


@pytest.mark.parametrize('declaration,diagnostic', [
    ('let x=int.max', 'mathematical int has no min or max'),
    ('let x=int.min', 'mathematical int has no min or max'),
    ('let x=1 transmute float64', 'transmute requires an explicit fixed-width type'),
    ('let xs=[1 2] let fixed:array<int64>=xs', 'type mismatch'),
])
def test_int_type_boundaries(compiler, tmp_path, declaration, diagnostic):
    source = tmp_path / 'identity.dewy'
    source.write_text(f'main=()=>{{{declaration}}}\n')
    result = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'identity'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr
