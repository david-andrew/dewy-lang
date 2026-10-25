"""SIMD maps preserve the scalar order of floating-point reductions."""
import os
import platform
import re
import subprocess

import pytest

from tests.support import compiler


@pytest.mark.parametrize('fields', [2, 4, 8])
@pytest.mark.parametrize('release', [False, True])
def test_record_folds_match_scalar_bits(compiler, tmp_path, fields, release):
    (tmp_path / 'bits.jo').write_text('bits = (x: f64) -> u64: f64_bits(x)\nfrombits = (x: u64) -> f64: f64_from_bits(x)\n')
    source = tmp_path / 'ordered.dewy'
    source.write_text('''
from p"bits.jo" import bits, frombits
R:type=[FIELDS]
f=(xs:array<R>):>array<float64>=>{
 let a:float64=-0.0 let b:float64=7.0 let c:float64=-3.0
 loop p in xs {
   a+=p.x0
   b=p.LAST+b
   c+=sqrt(p.LAST*p.LAST+0.25)/(p.LAST*p.LAST+1.0)
 }
 return [a b c]
}
main=(args:array<string>)=>{
 let n=int64(to_int(args[1]) ?? 0)
 let mode=int64(to_int(args[2]) ?? 0)
 let values:array<float64>=if mode =? 2 [frombits(0x7ff8000000000001) frombits(0x7ff8000000000002) 1.0 -0.0]
 else if mode =? 3 [frombits(0x7ff0000000000000) frombits(0xfff0000000000000) 0.0 -0.0]
 else [10000000000000000.0 1.0 -10000000000000000.0 1.0]
 let xs=[loop i in [0..n) R[INIT]]
 let r=f(xs)
 loop x in r {printl"{bits(x)}"}
}
$runtime_checks
'''.replace('FIELDS', ' '.join(f'x{i}:float64' for i in range(fields)))
        .replace('LAST', f'x{fields-1}')
        .replace('INIT', ' '.join(['if mode =? 1 -0.0 else values[i%4]'] +
                                 [f'if mode >=? 2 values[(i+1)%4] else (i%7-{j}) as float64' for j in range(1, fields)])))
    binaries = []
    for debug in (False, True):
        binary = tmp_path / ('scalar' if debug else 'vector')
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary,
                                *(['--release'] if release else []), *(['-g'] if debug else [])],
                               capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stderr
        if not debug and platform.machine().lower() in ('x86_64', 'amd64'):
            for ty in (4, 5):
                assert re.search(rf' = vbin .*c=9 imm=1 ty={ty}', built.stdout)
            assert re.search(r' = vbin .*c=10 imm=1 ty=1', built.stdout)
            assert re.search(r' = vbin .*c=11 imm=1 ty=1', built.stdout)
        binaries.append(binary)
    for n in (0, 1, 2, 3, 4, 5, 7, 8, 9, 15, 17, 33):
        for mode in (0, 1, 2, 3):
            expected = subprocess.run([binaries[1], str(n), str(mode)], capture_output=True,
                                      text=True, timeout=10)
            assert expected.returncode == 0, expected.stderr
            for sse in (False, True):
                env = dict(os.environ, DEWY_THREADS='1')
                env.pop('DEWY_NO_AVX', None)
                if sse:
                    env['DEWY_NO_AVX'] = '1'
                ran = subprocess.run([binaries[0], str(n), str(mode)], env=env,
                                     capture_output=True, text=True, timeout=10)
                assert ran.returncode == 0, ran.stderr
                # LANGUAGE permits NaN sign/payload differences, including
                # scalar register allocation swapping addition operands.
                got = list(map(int, ran.stdout.split()))
                want = list(map(int, expected.stdout.split()))
                def nan(bits):
                    return bits & 0x7ff0000000000000 == 0x7ff0000000000000 and bits & 0xfffffffffffff != 0
                assert len(got) == len(want)
                assert all(a == b or nan(a) and nan(b) for a, b in zip(got, want)), (fields, n, mode, sse)


def test_carried_dependency_stays_scalar(compiler, tmp_path):
    source = tmp_path / 'dependent.dewy'
    source.write_text('''
f=(xs:array<float64>):>float64=>{
 let a:float64=1.0 let b:float64=0.0
 loop x in xs {a+=x b+=a}
 return b
}
main=()=>{printl(f([1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0]))}
$runtime_checks
''')
    binary = tmp_path / 'dependent'
    built = subprocess.run([compiler, 'build', source, '--release', '--ir', '-o', binary],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert float(ran.stdout) == 128.0


def test_ordered_fold_spills(compiler, tmp_path):
    # More live accumulators than SIMD registers exercises both vector and
    # scalar spills in the ordered fold, including the reversed operand form.
    (tmp_path / 'bits.jo').write_text('bits = (x: f64) -> u64: f64_bits(x)\n')
    count = 16
    source = tmp_path / 'spills.dewy'
    source.write_text('from p"bits.jo" import bits\n'
                     'f=(xs:array<float64>):>array<float64>=>{\n' +
                     '\n'.join(f'let a{i}:float64={i}.0' for i in range(count)) +
                     '\nloop x in xs {\n' +
                     '\n'.join(f'a{i}=' + (f'a{i}+(x*{i+1}.0)' if i%2 == 0
                                           else f'(x*{i+1}.0)+a{i}') for i in range(count)) +
                     '\n}\nreturn [' + ' '.join(f'a{i}' for i in range(count)) + ']\n}\n'
                     'main=()=>{let r=f([1.0e16 1.0 -1.0e16 1.0 2.0 -3.0 0.0 8.0 1.0]) '
                     'loop x in r {printl"{bits(x)}"}}\n$runtime_checks\n')
    outputs = []
    for debug in (True, False):
        binary = tmp_path / ('scalar' if debug else 'vector')
        built = subprocess.run([compiler, 'build', source, '--release', '-o', binary,
                                *(['-g'] if debug else [])], capture_output=True, text=True, timeout=60)
        assert built.returncode == 0, built.stderr
        for sse in (False, True):
            env = dict(os.environ)
            env.pop('DEWY_NO_AVX', None)
            if sse:
                env['DEWY_NO_AVX'] = '1'
            ran = subprocess.run([binary], env=env, capture_output=True, text=True, timeout=10)
            assert ran.returncode == 0, ran.stderr
            outputs.append(ran.stdout)
    assert len(set(outputs)) == 1
