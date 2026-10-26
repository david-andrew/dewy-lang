"""Library contracts carry nonemptiness and positive rational denominators."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, *args):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *args, path.name], cwd=tmp_path,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('operation', ['min_by', 'max_by'])
def test_key_extrema_contract(compiler, tmp_path, operation):
    source = f'''pick=(xs:array<int64>):>int64 & no panics=>{{
    if xs.length =? 0 return 0
    return xs.{operation}((x:int64)=>x)
}}
printl(pick([3 1 2]))
printl(pick([]))
'''
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0, result.stderr
    assert result.stdout == ('1\n0\n' if operation == 'min_by' else '3\n0\n')


@pytest.mark.parametrize('operation', ['min_by', 'max_by'])
def test_key_extrema_missing_contract(compiler, tmp_path, operation):
    result = run(compiler, tmp_path,
                 f'pick=(xs:array<int64>)=>xs.{operation}((x:int64)=>x)\nprintl(pick([1]))\n', 'check')
    assert result.returncode != 0
    assert 'xs.length >? 0' in result.stderr, result.stderr


@pytest.mark.parametrize('operation', ['min_by', 'max_by'])
def test_key_extrema_empty_runtime_contract(compiler, tmp_path, operation):
    result = run(compiler, tmp_path,
                 f'$runtime_checks\npick=(xs:array<int64>)=>xs.{operation}((x:int64)=>x)\nprintl(pick([]))\n', 'run')
    assert result.returncode == 101, result.stderr
    assert 'refinement failed' in result.stderr and 'xs.length >? 0' in result.stderr


def test_key_extrema_panicking_callback(compiler, tmp_path):
    result = run(compiler, tmp_path, '''key=(x:int64):>int64=>{
    $runtime_checks
    return [1 2][x]
}
let values:array<int64>=[1 2]
printl(values.min_by(@key))
''', 'check')
    # The check belongs to this module even when a library calls the helper.
    assert result.returncode == 0, result.stderr


def test_round_rational_no_panics(compiler, tmp_path):
    result = run(compiler, tmp_path, '''rounded=(x:rational):>int & no panics=>round(x)
printl(rounded(5/2))
printl(rounded(-5/2))
''', 'run')
    assert result.returncode == 0 and result.stdout == '3\n-3\n', result.stdout + result.stderr


@pytest.mark.parametrize('type_name', ['rational', 'rational<int64>'])
@pytest.mark.parametrize('statement', ['let r:TYPE=1/2\nr.denominator=0', 'let r:TYPE=1/2\nr.denominator=-1'])
def test_rational_denominator_invariant(compiler, tmp_path, type_name, statement):
    result = run(compiler, tmp_path,
                 statement.replace('TYPE', type_name) + '\nprintl(r)\n', 'check')
    assert result.returncode != 0 and 'refinement' in result.stderr, result.stderr


@pytest.mark.parametrize('value, ok', [('3', True), ('-1', False), ('0', False), ('9223372036854775808', True)])
def test_constant_refinement_is_checked(compiler, tmp_path, value, ok):
    result = run(compiler, tmp_path, f'''$runtime_checks
Box:type=[value:int<(>? 0)>]
make=(n:int):>Box=>Box[n]
const BOX=make({value})
printl(BOX.value)
''', 'run')
    assert (result.returncode == 0) == ok, result.stderr
    if ok:
        assert result.stdout == value + '\n'
    else:
        assert 'refinement failed' in result.stderr, result.stderr


def test_raw_access_keeps_array_length(compiler, tmp_path):
    result = run(compiler, tmp_path, '''memset=(p:ptr<uint8> value:int32 count:uint64):>ptr<uint8>=>$extern
main=():>void=>$unsafe {
let bytes:array<uint8 length =? 4>=[1 2 3 4]
memset(bytes.ptr 0 4);
$assert bytes.length =? 4
printl(bytes[3])
}
''', 'run')
    assert result.returncode == 0 and result.stdout == '0\n', result.stdout + result.stderr


def test_raw_access_still_protects_refined_elements(compiler, tmp_path):
    result = run(compiler, tmp_path, '''main=():>void=>$unsafe {
let values:array<int64<(>? 0)> length =? 1>=[1]
let p=values.ptr
printl(p[0])
}
''', 'check')
    assert result.returncode != 0 and 'mutable refinement access' in result.stderr, result.stderr


def test_tcp_helpers_have_no_panics(compiler, tmp_path):
    result = run(compiler, tmp_path, '''import net
listen=():>(net.TcpListener|net.NetError) & no panics=>net.tcp_listen(0)
connect=():>(net.TcpStream|net.NetError|Canceled) & no panics=>net.tcp_connect("127.0.0.1" 1)
accept=(s:net.TcpListener):>(net.TcpStream|net.NetError|Canceled) & no panics=>net.tcp_accept(s)
send=(s:net.TcpStream):>(void|net.NetError|Canceled) & no panics=>net.tcp_send(s "hello")
receive=(s:net.TcpStream):>(array<uint8>|none|net.NetError|Canceled) & no panics=>net.tcp_receive(s)
# Demand each body without requiring a live network in this compiler test.
let a=@listen let b=@connect let c=@accept let d=@send let e=@receive
''', 'check')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('source, expected', [
    ('''take=(s:string<length =? 1>):>string=>s
const VALUE=take("é")
printl(VALUE)
''', 'é\n'),
    ('''take=(xs:array<int64 length >? 0>):>int64=>xs[0]
const VALUE=take([9])
printl(VALUE)
''', '9\n'),
])
def test_constant_contract_projections(compiler, tmp_path, source, expected):
    result = run(compiler, tmp_path, '$runtime_checks\n' + source, 'run')
    assert result.returncode == 0 and result.stdout == expected, result.stdout + result.stderr
