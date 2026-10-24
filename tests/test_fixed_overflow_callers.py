"""Counter exhaustion and long decimal runs must not silently wrap."""
from pathlib import Path
import subprocess

import pytest

from tests.support import compiler

RUNTIME_CHECKS = '\n$runtime_checks\n'

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('release', [False, True])
def test_chacha_counter_exhaustion(compiler, tmp_path, release):
    source = tmp_path / 'counter.dewy'
    source.write_text(f'''from p"{ROOT}/tests/ladder/96_ct_crypto/chacha.dewy" import Key, Nonce, xor_stream
main=(args:array<string>)=>{{
    let key:Key=[]
    let nonce:Nonce=[]
    let count=int64(to_int(args[1]) ?? 0)
    let data:array<uint8>=[]
    loop i in [0..count) data.push(0)
    printl(xor_stream(key uint32.max nonce data).length)
}}
''' + RUNTIME_CHECKS)
    binary = tmp_path / 'counter'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for count in (0, 1, 64):
        ran = subprocess.run([binary, str(count)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout.strip() == str(count)
    ran = subprocess.run([binary, '65'], capture_output=True, text=True)
    assert ran.returncode == 101, ran.stdout + ran.stderr
    assert not ran.stdout


@pytest.mark.parametrize('release', [False, True])
def test_text_long_digit_run(compiler, tmp_path, release):
    from tools.compiler.bench import prepare_source
    prepared = prepare_source('text', tmp_path)
    source = tmp_path / 'digits.dewy'
    source.write_text(f'''import p"{prepared}" as text
main=(args:array<string>)=>{{printl(text.kernel(args[1] as array<uint8>))}}
''' + RUNTIME_CHECKS)
    binary = tmp_path / 'digits'
    built = subprocess.run([compiler, 'build', source, '-o', binary] +
                           (['--release'] if release else []), capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    for digits in ('1234567', '9223372036854775808', '9' * 500):
        ran = subprocess.run([binary, digits], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        expected = (5 * 31**3 + int(digits)) % 1000000007
        assert ran.stdout.strip() == str(expected)
