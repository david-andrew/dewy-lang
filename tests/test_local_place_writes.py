"""A write through a local place (`let p = @r.xs`, `let p = @a[0]`,
`loop @row in a`) or a narrowed name (`if r is? T`) changes the variable it
names: facts about that variable end there, whether the write is a method, a
builtin or a call taking the place by `@`. A builtin's write to a global or an
`@` parameter may change any other of those."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

# (each: the program and the line of its one obligation the write leaves unproven)
REJECTED = {
    'field_clear': ('R:type=[xs:array<int64>]\nmain=()=>{\n    let a=R[[1 2]]\n    let p=@a.xs\n    p.clear()\n    printl(a.xs[1])\n}\n', 6),
    'field_guard': ('R:type=[xs:array<int64>]\nf=(r:R)=>{\n    let p=@r.xs\n    if r.xs.length >? 0 {\n        p.clear()\n        printl(r.xs[0])\n    }\n}\nmain=()=>f(R[[7]])\n', 6),
    'field_call': ('wipe=(@a:array<int64>)=>a.clear()\nR:type=[xs:array<int64>]\nmain=()=>{\n    let r=R[[7]]\n    let p=@r.xs\n    wipe(@p)\n    printl(r.xs[0])\n}\n', 7),
    'field_dict': ('R:type=[d:dict<string int64>]\nmain=()=>{\n    let r=R[["x"->7]]\n    let p=@r.d\n    p.clear()\n    printl(r.d["x"])\n}\n', 6),
    'field_pool': ('R:type=[p:Pool<int64>]\nmain=()=>{\n    let r=R[[]]\n    let h=r.p.add(7)\n    let q=@r.p\n    q.retain((x:int64)=>false)\n    printl(r.p[h])\n}\n', 7),
    'field_min': ('R:type=[xs:array<int64>]\nmain=()=>{\n    let r=R[[7]]\n    let p=@r.xs\n    if r.xs.length >? 0 {\n        p.clear()\n        printl(min(r.xs))\n    }\n}\n', 7),
    'element_clear': ('main=()=>{\n    let a=[[1 2] [3]]\n    let p=@a[0]\n    p.clear()\n    printl(a[0][1])\n}\n', 5),
    'element_call': ('wipe=(@r:array<int>)=>{r.clear()}\nmain=()=>{\n    let a=[[1 2 3] [4]]\n    let p=@a[0]\n    wipe(@p)\n    printl(a[0][2])\n}\n', 6),
    'entry_clear': ('main=()=>{\n    let d:dict<string dict<string int64>>=["k"->["x"->1]]\n    if "x" in? d["k"] {\n        let p=@d["k"]\n        p.clear()\n        printl(d["k"]["x"])\n    }\n}\n', 6),
    'element_pool': ('main=()=>{\n    let ps:array<Pool<int64>>=[[]]\n    let h=ps[0].add(3)\n    let q=@ps[0]\n    q.clear()\n    printl(ps[0][h])\n}\n', 6),
    'loop_element': ('main=()=>{\n    let a=[[1 2 3] [4]]\n    loop @row in a row.clear()\n    printl(a[0][2])\n}\n', 4),
    'loop_element_call': ('wipe=(@r:array<int>)=>{r.clear()}\nmain=()=>{\n    let a=[[1 2 3] [4]]\n    loop @row in a wipe(@row)\n    printl(a[0][2])\n}\n', 5),
    'field_hull': ('R:type=[xs:array<int>]\nmain=()=>{\n    let r=R[[loop x in [1 2] x]]\n    let p=@r.xs\n    p.push(1000)\n    let n:int8=0\n    loop x in r.xs n=x\n    printl(n)\n}\n', 7),
    # (a builtin's write to a global or an `@` parameter may change the other)
    'global_then_parameter': ('let g:array<int64>=[1 2 3]\nf=(@a:array<int64>)=>{ if a.length >? 2 { g.clear(); printl(a[2]) } }\nmain=()=>f(@g)\n', 2),
    'parameter_then_global': ('let g:array<int64>=[1 2 3]\nf=(@a:array<int64>)=>{ if g.length >? 2 { a.clear(); printl(g[2]) } }\nmain=()=>f(@g)\n', 2),
    # (a narrowed name writes its variable)
    'narrowed_clear': ('pick=(b:bool):>array<int64>|Missing=>if b [1 2 3] else Missing\nmain=()=>{\n    let r=pick(true)\n    if r is? Missing return\n    if r.length >? 2 { r.clear(); printl(r[2]) }\n}\n', 5),
    'narrowed_call': ('wipe=(@a:array<int64>)=>{a.clear()}\npick=(b:bool):>array<int64>|Missing=>if b [1 2 3] else Missing\nmain=()=>{\n    let r=pick(true)\n    if r is? Missing return\n    if r.length >? 2 { wipe(@r); printl(r[2]) }\n}\n', 6),
    'narrowed_optional': ('pick=(b:bool):>array<int64>?=>if b [1 2 3] else none\nmain=()=>{\n    let r=pick(true)\n    if r isnt? none and r.length >? 2 { r.clear(); printl(r[2]) }\n}\n', 4),
    'narrowed_field': ('R:type=[xs:array<int64>]\npick=(b:bool):>R|Missing=>if b R[[1 2 3]] else Missing\nmain=()=>{\n    let r=pick(true)\n    if r is? Missing return\n    if r.xs.length >? 2 { r.xs.clear(); printl(r.xs[2]) }\n}\n', 6),
}


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_place_write_ends_facts(compiler, tmp_path, name):
    source, line = REJECTED[name]
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode != 0, result.stdout
    errors = [text for text in result.stderr.splitlines() if ': error: ' in text]
    assert errors and errors[0].startswith(f'program.dewy:{line}:'), result.stderr


def test_place_push_grows_the_field(compiler, tmp_path):
    # (the push through the place is seen: index 2 exists afterwards)
    source = 'R:type=[xs:array<int64>]\nmain=()=>{\n    let a=R[[1 2]]\n    let p=@a.xs\n    p.push(3)\n    printl(a.xs[2])\n}\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '3\n', result.stdout + result.stderr


def test_narrowed_write_keeps_other_facts(compiler, tmp_path):
    # (a write through a narrowed name changes its variable alone)
    source = 'pick=(b:bool):>array<int64>|Missing=>if b [1 2 3] else Missing\nmain=()=>{\n    let r=pick(true)\n    if r is? Missing return\n    let n=[1 2 3]\n    r.clear()\n    printl(n[2] r.length)\n}\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == '3 0\n', result.stdout + result.stderr
