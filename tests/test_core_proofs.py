"""Checked erased proofs: no execution can rescue a missing static obligation."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

ORDERED = '''$proof
ordered=(a:int64 b:int64<v=>a <=? v> c:int64<v=>b <=? v>):><a <=? c>=>{
    $assert a <=? b
    $assert b <=? c
}
'''


def check(compiler, tmp_path, source):
    path = tmp_path / 'proof.dewy'
    path.write_text(source)
    return subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=30)


@pytest.mark.parametrize('source,diagnostic', [
    ('$proof\np=():><0 =? 0>=>{q()}\n$proof\nq=():><0 =? 0>=>{p()}\nmain=()=>p()', 'cyclic proof dependency'),
    (ORDERED + 'main=()=>{let x=ordered(0 1 2)}', 'cannot assign a value with no type (void)'),
    (ORDERED + 'main=()=>{let x=@ordered}', 'proof cannot be used as a value'),
    (ORDERED + 'runtime=():>int64=>{printl("effect"); return 0}\nmain=()=>ordered(runtime() 1 2)', 'pure fact terms'),
    (ORDERED + 'runtime=():>int64=>0\nmain=()=>ordered(runtime() 1 2)', 'pure fact terms'),
    ('$proof\np=(a:int64):><a >? 0>=>{}\nmain=()=>p(1)', 'cannot prove proof exit proposition'),
    ('$proof\np=(a:int64):><a >? 0>=>{if a >? 0 {return}; return}\nmain=()=>p(1)', 'proof exit proposition'),
    (ORDERED + 'main=()=>ordered(3 2 1)', 'proof precondition refuted'),
    (ORDERED + 'f=(a:int64 b:int64)=>ordered(a b b)\nmain=()=>f(1 2)', 'cannot prove proof precondition'),
    ('$proof\np=():><0 =? 0>=>{loop true {}}\nmain=()=>p()', 'bodies allow only'),
    ('$proof\np=(a:int64=1):><a =? a>=>{}\nmain=()=>p()', 'defaults and place parameters'),
    ('$proof\np=(@a:int64):><a =? a>=>{}\nmain=()=>{let a:int64=1; p(@a)}', 'defaults and place parameters'),
    ('$proof\np=():><0 =? 0>=>{printl("runtime")}\nmain=()=>p()', 'bodies allow only'),
    ('let global:int64=1\n$proof\np=():><0 =? 0>=>{$assert global >? 0}\nmain=()=>p()', 'globals cannot be erased'),
    ('$prototype\nmain=()=>{}', '$prototype` is part of the design but not implemented yet'),
])
def test_proof_negative_goldens(compiler, tmp_path, source, diagnostic):
    result = check(compiler, tmp_path, source + '\n')
    assert result.returncode != 0, result.stdout + result.stderr
    assert diagnostic in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_checked_proof_erasure(compiler, tmp_path, release):
    source = tmp_path / 'proof.dewy'
    source.write_text(ORDERED + '''$proof
transitive=(a:int64 b:int64<v=>a <=? v> c:int64<v=>b <=? v>):><a <=? c>=>{
    if a =? b {ordered(a b c); return}
    ordered(a b c)
}
f=(a:int64 b:int64<v=>a <=? v> c:int64<v=>b <=? v>):>int64=>{
    transitive(a b c)
    $assert a <=? c
    return 7
}
main=():>int64=>{return f(1 2 3)-7}
''')
    output = tmp_path / 'program'
    result = subprocess.run([compiler, 'build', source, '-o', output, '--ir',
                             *(['--release'] if release else [])], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ordered' not in result.stdout and 'transitive' not in result.stdout, result.stdout
    assert subprocess.run([output], timeout=10).returncode == 0


def test_proof_fact_invalidation(compiler, tmp_path):
    result = check(compiler, tmp_path, ORDERED + '''f=(a:int64 b:int64<v=>a <=? v> c:int64<v=>b <=? v>)=>{
    ordered(a b c)
    c=a-1
    $assert a <=? c
}
main=()=>f(1 2 3)
''')
    assert result.returncode != 0 and 'assertion' in result.stderr, result.stderr

POSITIVE = '''positive=(a:int64):>true & <a >? 0> | false & <a <=? 0>=>{
    if a >? 0 {return true}
    return false
}
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('body,success', [
    ('let r=positive(a); if r {$assert a >? 0} else {$assert a <=? 0}', True),
    ('let r=positive(a); if r =? true {$assert a >? 0}', True),
    ('let r=positive(a); if not r {$assert a <=? 0}', True),
    ('let r=positive(a); if r {$assert a >? 0} else {$assert a >? 0}', False),
    ('let r=positive(a); if r {$assert a >? 0}; $assert a >? 0', False),
    ('let r=positive(a); r=true; if r {$assert a >? 0}', False),
    ('let r=positive(a); if r {r=true; $assert a >? 0}', False),
    ('let r=positive(a); a=-1; if r {$assert a >? 0}', False),
    ('let r=positive(a); if flag {r=true}; if r {$assert a >? 0}', False),
    ('let r=positive(a); if flag {} else {}; if r {$assert a >? 0}', True),
])
def test_conditional_result_facts(compiler, tmp_path, body, success):
    result = check(compiler, tmp_path, POSITIVE + 'f=(a:int64 flag:bool)=>{' + body + '}\nmain=()=>f(4 true)\n')
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if not success:
        assert 'assertion' in result.stderr, result.stderr


@pytest.mark.parametrize('release', [False, True])
def test_union_result_facts(compiler, tmp_path, release):
    source = tmp_path / 'union.dewy'
    source.write_text('''Yes:type=[]
No:type=[]
positive=(a:int64):>Yes & <a >? 0> | No & <a <=? 0>=>{
    if a >? 0 {return Yes[]}
    return No[]
}
f=(a:int64):>int64=>{
    let r=positive(a)
    if r is? Yes {$assert a >? 0; return 1}
    else {$assert a <=? 0; return 0}
}
main=():>int64=>{return f(2)+f(-2)-1}
''')
    output = tmp_path / 'program'
    result = subprocess.run([compiler, 'build', source, '-o', output,
                             *(['--release'] if release else [])], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert subprocess.run([output], timeout=10).returncode == 0


@pytest.mark.parametrize('source', [
    'bad=(a:int64):>true & <a >? 0> | false=>true\nmain=():>void=>{bad(1)}',
    'bad=(a:int64):>true & <a >? 0> | false=>{a=1; return true}\nmain=():>void=>{bad(1)}',
    'Yes:type=[]\nNo:type=[]\nbad=(a:int64):>Yes & <a >? 0> | No=>Yes[]\nmain=():>void=>{bad(1)}',
])
def test_conditional_exit_obligation(compiler, tmp_path, source):
    result = check(compiler, tmp_path, source + '\n')
    assert result.returncode != 0 and 'result proposition' in result.stderr, result.stdout + result.stderr


def test_imported_generic_proof(compiler, tmp_path):
    (tmp_path / 'lemmas.dewy').write_text('''$proof
ordered=<T>(a:T b:T<v=>a <=? v> c:T<v=>b <=? v>):><a <=? c>=>{
    $assert a <=? b
    $assert b <=? c
}
positive=<T>(a:T):>true & <a >? 0> | false & <a <=? 0>=>a >? 0
''')
    result = check(compiler, tmp_path, '''from p"lemmas.dewy" import ordered, positive
f=(a:int64 b:int64<v=>a <=? v> c:int64<v=>b <=? v>)=>{
    ordered(a b c)
    $assert a <=? c
    if positive(a) {$assert a >? 0}
}
main=()=>{f(1 2 3); ordered<uint64>(9223372036854775808 9223372036854775809 18446744073709551615)}
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('body,success', [
    ('let r=positive(a); if r is? Yes {$assert a >? 0}', True),
    ('let r=positive(a); if r is? Yes {} else {$assert a >? 0}', False),
    ('let r=positive(a); r=Yes[]; if r is? Yes {$assert a >? 0}', False),
    ('let r=positive(a); if r is? Yes {$assert a >? 0}; $assert a >? 0', False),
])
def test_union_result_invalidations(compiler, tmp_path, body, success):
    result = check(compiler, tmp_path, '''Yes:type=[]
No:type=[]
positive=(a:int64):>Yes & <a >? 0> | No=>{if a >? 0 {return Yes[]}; return No[]}
f=(a:int64)=>{''' + body + '}\nmain=()=>f(4)\n')
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    if not success:
        assert 'assertion' in result.stderr, result.stderr


@pytest.mark.parametrize('body,success', [
    ('let r=positive(a); if r not=? none {$assert a >? 0}', True),
    ('let r=positive(a); if r =? none {$assert a >? 0}', False),
    ('let r=positive(a); r=1; if r not=? none {$assert a >? 0}', False),
])
def test_optional_result_facts(compiler, tmp_path, body, success):
    result = check(compiler, tmp_path, '''positive=(a:int64):>int64 & <a >? 0> | none=>{
    if a >? 0 {return a}; return none
}
f=(a:int64)=>{''' + body + '}\nmain=()=>f(4)\n')
    assert (result.returncode == 0) == success, result.stdout + result.stderr


@pytest.mark.core_quick
@pytest.mark.parametrize('source,diagnostic', [
    ('$proof\nmain=():>void=>{}', 'proof cannot be a runtime entry point'),
    ('$proof\np=(a:int64):><a >? 0>=>{}\nmain=()=>{}', 'cannot prove proof exit proposition'),
    ('$proof\np=():><0 =? 0>=>{$unsafe_assume true}\nmain=()=>{p()}', '$unsafe_assume'),
    ('bad=(a:int64):>true & <a >? 0>=>false\nmain=():>void=>{bad(1)}', 'declared boolean result arm'),
    ('bad=():>true=>false\nmain=():>void=>{bad()}', 'declared boolean result arm'),
])
def test_proof_and_result_boundaries(compiler, tmp_path, source, diagnostic):
    result = check(compiler, tmp_path, source + '\n')
    assert result.returncode != 0 and diagnostic in result.stderr, result.stdout + result.stderr


def test_void_proof_result(compiler, tmp_path):
    result = check(compiler, tmp_path, '''$proof
p=(a:int64<v=>v >? 0>):>void & <a >? 0>=>{}
f=(a:int64<v=>v >? 0>)=>{p(a); $assert a >? 0}
main=()=>f(1)
''')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('source', [
    'positive=int64<i=>i >? 0>\n$proof\np=(a:int64):><a =? a>=>{}\nf=(a:int64)=>{p(a as positive)}\nmain=()=>f(1)',
    'positive=int64<i=>i >? 0>\n$proof\np=(a:int64):><a >? 0>=>{$assert (a as positive) >? 0}\nmain=()=>p(1)',
])
def test_erased_refinement_cast_needs_static_evidence(compiler, tmp_path, source):
    result = check(compiler, tmp_path, source + '\n')
    assert result.returncode != 0 and 'cannot prove refinement' in result.stderr, result.stdout + result.stderr
