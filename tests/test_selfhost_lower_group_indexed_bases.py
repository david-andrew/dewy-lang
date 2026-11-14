"""Cached array element bases preserve snapshots, resizing and checked failures."""
import subprocess

from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401


PROGRAM = '''$runtime_checks
Word:type=int64<overflow='wrap'>
Item:type=[op:int32 dst:int32 a:int32 b:int32 imm:int64 pad0:int64 pad1:int64]
scan=(code:array<Item>):>Word=>{
    let result:Word=0
    loop i in [Word(0)..Word(code.length)) {
        let ins=code[i]
        if ins.op not=? 77 {continue}
        result+=i+Word(ins.dst)
    }
    result
}
replace=(@xs:array<int64>):>void=>{
    loop i in [0..xs.length) {xs[i]+=1}
}
grow=(@xs:array<int64>):>void=>{
    loop i in [0..xs.length) {
        xs.push(9)
        xs[i]+=1
    }
}
main=()=>{
    printl(scan([]))
    let code:array<Item>=[]
    loop i in [0..32) {
        code.push(Item[op=int32(if i%7 =? 0 {77} else {0}) dst=int32(i)
                       a=0 b=0 imm=0 pad0=0 pad1=0])
    }
    printl(scan(code))
    let xs:array<int64>=[1 2 3]
    let snapshot=xs
    replace(@xs)
    printl(xs)
    printl(snapshot)
    grow(@xs)
    printl(xs)
    let empty:array<int64>=[]
    replace(@empty)
    grow(@empty)
    printl(empty)
}
'''

FAILURE = '''$runtime_checks
main=()=>{
    let xs:array<int64>=[1 2 3]
    loop i in [0..xs.length) {
        if i =? 1 {xs.truncate(1)}
        printl(xs[i])
    }
}
'''


def test_lower_group_indexed_bases_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    good = tmp_path / 'stable.dewy'
    bad = tmp_path / 'resize.dewy'
    good.write_text(PROGRAM)
    bad.write_text(FAILURE)
    compare_builds(compiler, tmp_path, monkeypatch, ('lower_group',),
                   (good, bad), flags=((), ('--release',)))
    for mode in range(2):
        ran = subprocess.run([tmp_path / 'dewy' / f'p0-{mode}'],
                             capture_output=True, text=True, timeout=15)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == '0\n140\n[2 3 4]\n[1 2 3]\n[3 4 5 9 9 9]\n[]\n'
        ran = subprocess.run([tmp_path / 'dewy' / f'p1-{mode}'],
                             capture_output=True, text=True, timeout=15)
        assert ran.returncode != 0
        assert ran.stdout == '1\n'
        assert 'bounds' in ran.stderr.lower(), ran.stderr
