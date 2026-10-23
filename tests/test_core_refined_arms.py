"""A refined arm of an optional or union result (`addr<i => i <? xs.length> | none`)
is proven at each return, from loops too, and its predicate holds once a
caller's test establishes that arm."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''$runtime_checks=false
find=(xs:array<int64> needle:int64):>addr<i => i <? xs.length> | none=>{
    loop i in [0..xs.length) {
        if xs[i] =? needle return i
    }
    return none
}
read=(xs:array<int64> needle:int64):>int64=>{
    let index=find(xs needle)
    if index is? addr return xs[index]
    return -1
}
main=():>void=>{
    let xs:array<int64>=[4 9 16]
    let total:int64=0
    loop x in [9 5] {total+=read(xs x)}
    printl("{total} {xs.length}")
}
'''


def test_refined_arm_facts(compiler, tmp_path):
    (tmp_path / 'arms.dewy').write_text(SOURCE)
    result = subprocess.run([compiler, 'run', 'arms.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)
    assert result.returncode == 0 and result.stdout == '8 3\n', result.stdout + result.stderr


def test_refined_arm_needs_its_test(compiler, tmp_path):
    source = SOURCE.replace('if index is? addr return xs[index]', 'return xs[index ?? 0]')
    (tmp_path / 'arms.dewy').write_text(source)
    result = subprocess.run([compiler, 'check', 'arms.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)
    assert result.returncode != 0 and 'cannot prove index is in bounds' in result.stderr, result.stderr


ERRORS = '''$runtime_checks=false
Failure:type=type of error & [offset:int64 message:string]
next=(source:array<uint8> start:int64<0 <=? start and start <=? source.length>):>int64<r => 0 <=? r and r <=? source.length>|Failure=>{
    if start <? source.length return start+1
    return Failure[start "end"]
}
# (a counter guarded at an offset from a symbolic start, stepping unevenly)
pairs=(source:array<uint8> start:int64<0 <=? start and start <=? source.length>):>int64=>{
    let i=start
    let n=0
    loop i+1 <? source.length {
        if source[i] =? source[i+1] {
            n+=1
            i+=2
        } else {
            i+=1
        }
    }
    return n
}
twice=(source:array<uint8>):>int64|Failure=>{
    let i=next(source 0) or_throw
    let j=next(source i) or_throw
    return j+pairs(source j)
}
main=():>void=>{
    let r=twice(bytes("aabb"))
    if r is? int64 printl(r)
}
'''


def test_refined_union_arms_and_offset_counters(compiler, tmp_path):
    (tmp_path / 'arms.dewy').write_text(ERRORS)
    result = subprocess.run([compiler, 'run', 'arms.dewy'], text=True, capture_output=True, timeout=60, cwd=tmp_path)
    assert result.returncode == 0 and result.stdout == '3\n', result.stdout + result.stderr
