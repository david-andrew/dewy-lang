"""Fixed-width overflow policies are types and callable integer conversions."""
import subprocess

import pytest

from tests.support import compiler

RUNTIME_CHECKS = '\n$runtime_checks\n'


@pytest.mark.parametrize('release', [False, True])
def test_policy_conversions(compiler, tmp_path, release):
    source = tmp_path / 'policy.dewy'
    source.write_text('''
W:type=uint8<overflow='wrap'>
S:type=int8<overflow='saturate'>
main=(args:array<string>)=>{
    let x=to_int(args[1]) ?? 0
    printl"{W(x)} {S(x)} {uint64<overflow='wrap'>(x)} {uint64<overflow='saturate'>(x)}"
    let word:int64=int64(to_int(args[2]) ?? 0)
    let unsigned:uint64=uint64.max
    printl"{W(word)} {S(word)} {int64<overflow='saturate'>(unsigned)}"
}
''' + RUNTIME_CHECKS)
    binary = tmp_path / 'policy'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), text=True, capture_output=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for x, word in [(-1, -129), (256, 128), (2**100 + 7, 127), (-2**100 - 3, -128)]:
        ran = subprocess.run([binary, str(x), str(word)], text=True, capture_output=True)
        assert ran.returncode == 0, ran.stderr
        sat = lambda n: min(127, max(-128, n))
        assert ran.stdout.splitlines() == [
            f'{x % 256} {sat(x)} {x % 2**64} {min(2**64-1, max(0, x))}',
            f'{word % 256} {sat(word)} {2**63-1}',
        ]


@pytest.mark.parametrize('source, diagnostic', [
    ('let x=wrap<uint8>(257)', "unknown"),
    ("let x:uint8<overflow='oops'>=1", 'overflow='),
    ("let x:int<overflow='wrap'>=1", 'fixed-width'),
    ("let x=uint8<overflow='wrap'>(1.5)", 'requires an integer'),
])
def test_policy_rejections(compiler, tmp_path, source, diagnostic):
    path = tmp_path / 'bad.dewy'
    path.write_text('main=()=>{' + source + '}\n')
    result = subprocess.run([compiler, 'check', path], text=True, capture_output=True)
    assert result.returncode != 0
    assert diagnostic in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_mathematical_power_with_word_exponent(compiler, tmp_path, release):
    source = tmp_path / 'power.dewy'
    source.write_text("""main=(args:array<string>)=>{
    let b:int=to_int(args[1]) ?? 0
    let e:int64=int64(to_int(args[2]) ?? 0)
    printl(b^e)
}
""" + RUNTIME_CHECKS)
    binary = tmp_path / 'power'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), text=True, capture_output=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for base, exponent in [(2, 100), (-2, 101), (0, 0), (3, 70)]:
        ran = subprocess.run([binary, str(base), str(exponent)], text=True, capture_output=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.strip() == str(base**exponent)


def test_policy_comptime(compiler, tmp_path):
    source = tmp_path / 'constant.dewy'
    source.write_text("""const low=uint8<overflow='wrap'>(1267650600228229401496703205383)
const high=int8<overflow='saturate'>(1267650600228229401496703205383)
const negative=uint64<overflow='saturate'>(-1267650600228229401496703205383)
main=()=>{printl"{low} {high} {negative}"}
""")
    binary = tmp_path / 'constant'
    built = subprocess.run([compiler, 'build', source, '-o', binary], text=True, capture_output=True)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], text=True, capture_output=True)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == '7 127 0'


@pytest.mark.parametrize('target', ['native', 'wasm'])
@pytest.mark.parametrize('release', [False, True])
def test_saturating_arithmetic(compiler, tmp_path, target, release):
    from tests.support import Scripts
    import shutil
    functions = []
    for signed in (False, True):
        for bits in (8, 16, 32, 64):
            name = ('int' if signed else 'uint') + str(bits)
            ty = name + "<overflow='saturate'>"
            functions.append(f'''{name}_ops=(x:int y:int)=>{{
    let a:{ty}={ty}(x)
    let b:{ty}={ty}(y)
    let sum=a sum+=b
    let product=a product*=b
    let difference=a difference-=b
    printl"{{a+b}} {{a-b}} {{a*b}} {{-a}} {{sum}} {{difference}} {{product}}"
}}''')
    source = tmp_path / 'saturate.dewy'
    source.write_text('\n'.join(functions) + '''
main=(args:array<string>)=>{
    let x=to_int(args[1]) ?? 0
    let y=to_int(args[2]) ?? 0
''' + '\n'.join(f'{name}_ops(x y)' for name in
                [f'{prefix}{bits}' for prefix in ('uint', 'int') for bits in (8, 16, 32, 64)]) + '\n}\n' + RUNTIME_CHECKS)
    binary = tmp_path / ('saturate.html' if target == 'wasm' else 'saturate')
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []) +
                           (['--target', 'wasm32'] if target == 'wasm' else []),
                           text=True, capture_output=True)
    assert built.returncode == 0, built.stdout + built.stderr
    command = [binary]
    if target == 'wasm':
        node = shutil.which('node')
        if not node:
            pytest.skip('node is needed for wasm execution')
        parser = Scripts()
        parser.feed(binary.read_text())
        runner = tmp_path / 'runner.js'
        runner.write_text('const dewyArgs = process.argv.slice(1);\n' + '\n'.join(parser.parts))
        command = [node, runner]
    for x, y in [(127, 1), (255, 2), (-128, -1), (2**63-1, 2), (-2**63, -1),
                 (2**64-1, 2), (1, 2**64-1), (-2**63, -2**63), (0, 0)]:
        ran = subprocess.run([*command, str(x), str(y)], text=True, capture_output=True)
        assert ran.returncode == 0, ran.stderr
        expected = []
        for signed in (False, True):
            for bits in (8, 16, 32, 64):
                lo = -2**(bits-1) if signed else 0
                hi = 2**(bits-int(signed))-1
                clamp = lambda v: max(lo, min(hi, v))
                a, b = clamp(x), clamp(y)
                expected.append(' '.join(str(clamp(v)) for v in
                                         [a+b, a-b, a*b, -a, a+b, a-b, a*b]))
        assert ran.stdout.splitlines() == expected, (x, y, ran.stdout, expected)


@pytest.mark.parametrize('release', [False, True])
def test_policy_floor_power_abs(compiler, tmp_path, release):
    source = tmp_path / 'operators.dewy'
    source.write_text("""S:type=int8<overflow='saturate'>
W:type=uint8<overflow='wrap'>
L:type=int64<overflow='saturate'>
main=(args:array<string>)=>{
    let a:S=S(to_int(args[1]) ?? 0)
    let b:S=S(to_int(args[2]) ?? 1)
    let e:int64=int64(to_int(args[3]) ?? 0)
    let x:W=W(2)
    let minimum:L=L(int64.min)
    printl"{a//b} {a%b} {a^e} {abs(a)} {x^e} {minimum//L(-1)} {abs(minimum)} {a<<e}"
}
""" + RUNTIME_CHECKS)
    binary = tmp_path / 'operators'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), text=True, capture_output=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for a, b, exponent in [(-128, -1, 1), (-7, 3, 3), (7, -3, 2), (2, 3, 8)]:
        ran = subprocess.run([binary, str(a), str(b), str(exponent)], text=True, capture_output=True)
        assert ran.returncode == 0, ran.stderr
        clamp = lambda v: min(127, max(-128, v))
        expected = [clamp(a//b), a%b, clamp(a**exponent), clamp(abs(a)), 2**exponent % 256,
                    2**63-1, 2**63-1, clamp(a << exponent)]
        assert ran.stdout.strip() == ' '.join(map(str, expected))
