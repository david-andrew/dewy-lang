"""Scoped storage addresses cannot become ordinary escaping integers."""
import subprocess

import pytest

from tests.support import compiler, build_case_batch  # noqa: F401
from pathlib import Path


def run(compiler, tmp_path, source, command='check', release=False):
    path = tmp_path / 'loan.dewy'
    path.write_text(source)
    args = [str(compiler)]
    if command == 'check':
        args += ['check', str(path)]
    else:
        args += [str(path)]
    if release:
        args += ['--release']
    return subprocess.run(args, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize('body', [
    '__load_i64__(bytes)',
    'return __load_i64__(bytes)',
    'outside=__load_i64__(bytes)',
    'global_address=__load_i64__(bytes)',
    'let p=__load_i64__(bytes); let record=[address=p]; 0',
    'let p=__load_i64__(bytes); let f=():>int64=>p; 0',
    'let p=__load_i64__(bytes); let flag=(p >? 0) and {outside=1; true}; 0',
    'bytes.push(2); 0',
    'bytes=[9]; 0',
    'let copy=bytes; 0',
    '$lend(bytes) {0}',
    'let p=__load_i64__(bytes); __store_u8__(p p); 0',
    'let p=__load_i64__(bytes); identity(p)',
    'let p=__load_i64__(bytes); (p as uint8) as int64',
    'let p=__load_i64__(bytes); if p >? 0 {outside=1}; 0',
    'let p=__load_i64__(bytes); let q:int64=0; loop i in [0..2) {outside=q; q=p}; 0',
    '__store_u8__(9 __load_i64__(bytes)); 0',
    'bytes.set_length(0); 0',
])
def test_loan_escape_and_stability(compiler, tmp_path, body):
    source = ('let global_address:int64=0\nidentity=(n:int64):>int64=>n\n'
              'main=()=>{let bytes:array<uint8>=[1 2]; let outside:int64=0; '
              'let result=$lend(bytes) {' + body + '}; printl(result)}\n')
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0, result.stdout
    assert 'loan' in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_writable_snapshot_and_early_exits(compiler, tmp_path, release):
    source = '''probe=(stop:bool):>int64=>{
    let bytes:array<uint8>=[1 2]
    let saved=bytes.copy()
    $lend(@bytes reserve=2) {
        let p=__load_i64__(bytes)
        __store_u8__(9 p)
        __store_u8__(7 p+2)
        bytes.set_length(3)
        if stop {return __load_u8__(p) as int64}
    }
    $runtime_assert saved[0] =? 1
    $runtime_assert saved.length =? 2
    $runtime_assert bytes.length =? 3
    return (bytes[0] as int64)+(bytes[2] as int64)
}
main=()=>{printl("{probe(false)} {probe(true)}")}
$runtime_checks
'''
    result = run(compiler, tmp_path, source, 'run', release)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '16 9\n'


def test_disjoint_nested_and_loop_exits(compiler, tmp_path):
    source = '''main=()=>{
    let a:array<uint8>=[1]
    let b:array<uint8>=[2]
    loop i in [0..3) {
        $lend(a) {
            $lend(@b) {__store_u8__(3 __load_i64__(b))}
            if i =? 0 {continue}
            break
        }
    }
    printl("{a[0]} {b[0]}")
}
'''
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0, result.stderr
    assert result.stdout == '1 3\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('reservation,length', [('0', '3'), ('2', '5'), ('0', '-1'), ('-1', '0'), ('9223372036854775807', '0')])
def test_reservation_bounds(compiler, tmp_path, reservation, length):
    source = ('main=()=>{let bytes:array<uint8>=[1 2]; $lend(@bytes reserve='
              + reservation + ') {bytes.set_length(' + length + ')}}\n')
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode != 0
    assert 'loan' in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize('target', ['native', 'wasm'])
def test_ladder_loan_backends(compiler, tmp_path, release, target):
    source = (Path(__file__).parent / 'ladder/79_scoped_byte_loan/design.dewy').read_text()
    command, error = build_case_batch(compiler, tmp_path, {'loan': source},
                                     ['case_0()'], release, target)
    assert error is None, error
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '1680 39\n'


def test_hidden_alias_loan_rejected(compiler, tmp_path):
    source = '''let bytes:array<uint8>=[1 2]
change=()=>{bytes=[9]}
probe=(@value:array<uint8>)=>{
    $lend(value) {change(); __load_u8__(__load_i64__(value))}
}
main=()=>probe(@bytes)
'''
    result = run(compiler, tmp_path, source)
    assert result.returncode != 0 and 'loan' in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_dynamic_length_checked_in_release(compiler, tmp_path, release):
    result = run(compiler, tmp_path, '''probe=(n:int64)=>{
    let bytes:array<uint8>=[1 2]
    $lend(@bytes) {bytes.set_length(n)}
}
main=()=>probe(3)
$runtime_checks
''', 'run', release)
    assert result.returncode != 0
    assert 'scoped loan length exceeds reservation' in result.stderr, result.stderr


def test_mixed_origins_do_not_upgrade_readonly(compiler, tmp_path):
    result = run(compiler, tmp_path, '''probe=(flag:bool)=>{
    let a:array<uint8>=[1]
    let b:array<uint8>=[2]
    $lend(a) {
        let readonly=__load_i64__(a)
        $lend(@b) {
            let p=__load_i64__(b)
            if flag {p=readonly}
            __store_u8__(9 p)
        }
    }
}
main=()=>probe(true)
''')
    assert result.returncode != 0 and 'readonly loan' in result.stderr, result.stderr


def test_empty_loans(compiler, tmp_path):
    result = run(compiler, tmp_path, '''main=()=>{
    let bytes:array<uint8>=[]
    $lend(bytes) {let address=__load_i64__(bytes)}
    $lend(@bytes) {bytes.set_length(0)}
    bytes.push(7)
    printl(bytes[0])
}
''', 'run')
    assert result.returncode == 0 and result.stdout == '7\n', result.stderr
