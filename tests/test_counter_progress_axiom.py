"""The 64-bit progress assumption is scoped and can require real proofs."""
import subprocess

import pytest

from tests.support import compiler


def check(compiler, tmp_path, source):
    path = tmp_path / 'progress.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], capture_output=True, text=True)


@pytest.mark.parametrize('kind', ['int64', 'uint64'])
def test_progress_default_and_optout(compiler, tmp_path, kind):
    body = f'''$runtime_checks=false
f=(step:{kind}):>{kind}=>{{
    let count:{kind}=0
    loop i in [0..10) {{count+=step}}
    return count
}}
main=()=>printl(f(1))
'''
    normal = check(compiler, tmp_path, body)
    assert normal.returncode == 0, normal.stderr
    strict = check(compiler, tmp_path, '$no_assumed_bounds\n' + body)
    assert strict.returncode != 0 and f'fits {kind}' in strict.stderr


@pytest.mark.parametrize('kind', ['int32', 'uint32', 'int8'])
def test_narrow_counters_never_assumed(compiler, tmp_path, kind):
    result = check(compiler, tmp_path, f'''$runtime_checks=false
f=(step:{kind}):>{kind}=>{{let count:{kind}=0; loop i in [0..10) {{count+=step}}; return count}}
main=()=>printl(f(1))
''')
    assert result.returncode != 0 and f'fits {kind}' in result.stderr


def test_progress_optout_accepts_real_proof(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$no_assumed_bounds
$runtime_checks=false
f=(n:int64):>int64=>{
    let count:int64=0
    loop count <? n {count+=1}
    return count
}
main=()=>printl(f(10))
''')
    assert result.returncode == 0, result.stderr


def test_progress_nested_scope(compiler, tmp_path):
    prefix = '''$runtime_checks=false
f=(step:int64):>int64=>{
    let count:int64=0
    loop i in [0..10) {
        $no_assumed_bounds
        count+=step
    }
    return count
}
main=()=>printl(f(1))
'''
    result = check(compiler, tmp_path, prefix)
    assert result.returncode != 0 and 'fits int64' in result.stderr
    restored = prefix.replace('$no_assumed_bounds', '$no_assumed_bounds=false')
    result = check(compiler, tmp_path, '$no_assumed_bounds\n' + restored)
    assert result.returncode == 0, result.stderr


def test_progress_optout_retains_overflow_trap(compiler, tmp_path):
    source = tmp_path / 'progress.dewy'
    source.write_text(('''$no_assumed_bounds
main=(args:array<string>)=>{
    let count=int64(to_int(args[1]) ?? 0)
    count+=1
    printl(count)
}
''') + "\n$runtime_checks\n")
    binary = tmp_path / 'progress'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    good = subprocess.run([binary, '5'], capture_output=True, text=True)
    assert good.returncode == 0 and good.stdout.strip() == '6'
    bad = subprocess.run([binary, str(2**63-1)], capture_output=True, text=True)
    assert bad.returncode != 0 and not bad.stdout


@pytest.mark.parametrize('kind', ['int64', 'int32'])
def test_temporary_field_progress_obeys_width_and_optout(compiler, tmp_path, kind):
    body = f'''$runtime_checks=false
P:type=[x:{kind} step:{kind}]
f=(@p:P):>void=>{{let next=p.x+p.step;p.x=next}}
main=()=>{{let p=P(0 1);f(@p)}}
'''
    normal = check(compiler, tmp_path, body)
    assert (normal.returncode == 0) == (kind == 'int64'), normal.stderr
    strict = check(compiler, tmp_path, '$no_assumed_bounds\n' + body)
    assert strict.returncode != 0 and f'fits {kind}' in strict.stderr, strict.stderr


def test_temporary_progress_does_not_follow_changed_index(compiler, tmp_path):
    source = tmp_path / 'changed.dewy'
    source.write_text('''$runtime_checks
main=()=>{
let xs:array<int64>=[9223372036854775807 0]
let i:int64=0
let next=xs[i]+1
i=1
xs[i]=next
printl(xs)
}
''')
    binary = tmp_path / 'changed'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
    if built.returncode:
        assert 'fits int64' in built.stderr or 'overflow' in built.stderr, built.stderr
    else:
        ran = subprocess.run([binary], capture_output=True, text=True)
        assert ran.returncode == 101 and not ran.stdout
