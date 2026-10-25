"""Pool handle membership: `pool[h]`, `pool[h] = x` and `pool[h].field op= x`
need `pool.has(h)`, proven from the handle's `add` or a `has` guard while
nothing can have removed it since, else a compile error without runtime
checks. `remove` of a provably different handle, stores and loops that do not
remove keep it; copies keep the memberships they were made with."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

PROVEN = '''$runtime_checks=false
Enemy:type=[name:string health:int64=100]
World:type=[enemies:Pool<Enemy> turn:int64=0]
total=(enemies:Pool<Enemy> hs:array<Handle>):>int64=>{
    let sum:int64=0
    loop h in hs {
        if not enemies.has(h) continue
        sum=enemies[h].health
    }
    return sum
}
main=(argv:array<string>):>void=>{
    let enemies:Pool<Enemy>=[]
    let scout=enemies.add(Enemy[name="scout"])
    let guard=enemies.add(Enemy[name="guard" health=50])
    let before=enemies
    enemies[guard].health-=5
    enemies.remove(scout);
    let spare=enemies.add(Enemy[name="spare"])
    enemies[spare]=Enemy[name="replacement" health=7]
    if argv.length >? 3 {enemies.remove(spare);}
    let n=argv.length+2
    loop n >? 0 {
        n-=1
        enemies[guard].health-=1
    }
    loop i in [0..3) {enemies[guard].health-=1}
    printl"{enemies[guard].health} {before[scout].name} {before[guard].health} {enemies.has(scout)}"
    printl"{total(enemies [scout guard spare])} {enemies.get(scout)}"
    let world=World[enemies]
    let boss=world.enemies.add(Enemy[name="boss" health=900])
    world.enemies[boss].health-=1
    printl"{world.enemies[boss].health} {world.enemies[guard].name}"
}
'''

# (each: the program and the line of its one unproven membership)
REJECTED = {
    'removed': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    p.remove(a);\n    printl(p[a])\n}\n', 5),
    'store_removed': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    p.remove(a);\n    p[a]=2\n}\n', 5),
    'direct_removed': ('Item:type=[hp:int64]\nmain=():>void=>{\n    let p:Pool<Item>=[]\n    let a=p.add(Item[1])\n    p.remove(a);\n    p[a].hp-=1\n}\n', 6),
    'parameter': ('f=(p:Pool<int64> h:Handle):>int64=>p[h]\nmain=():>void=>printl(f([] Handle()))\n', 1),
    # (removing a handle not known to differ: it may be this one)
    'unknown_removed': ('f=(p:Pool<int64> x:Handle):>int64=>{\n    let q=p\n    let a=q.add(1)\n    q.remove(x);\n    return q[a]\n}\nmain=():>void=>printl(f([] Handle()))\n', 5),
    'guarded_removed': ('f=(p:Pool<int64> g:Handle):>int64=>{\n    let q=p\n    let a=q.add(1)\n    if not q.has(g) return 0\n    q.remove(g);\n    return q[a]\n}\nmain=():>void=>printl(f([] Handle()))\n', 6),
    # (another pool's handle can equal this pool's)
    'other_pool': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let q:Pool<int64>=[]\n    let a=p.add(1)\n    let b=q.add(2)\n    p.remove(b);\n    printl(p[a])\n}\n', 7),
    'copy_removed': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    let q=p\n    q.remove(a);\n    printl(p[a])\n    printl(q[a])\n}\n', 7),
    'cleared': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    p.clear()\n    printl(p[a])\n}\n', 5),
    'retained': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    p.retain((x:int64)=>x >? 5)\n    printl(p[a])\n}\n', 5),
    'branch_removes': ('main=(argv:array<string>):>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    if argv.length >? 1 {p.remove(a);}\n    printl(p[a])\n}\n', 5),
    'loop_removes': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    let hs=[a]\n    loop h in hs {p.remove(h);}\n    printl(p[a])\n}\n', 6),
    'while_removes': ('main=(argv:array<string>):>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    let n=argv.length\n    loop n >? 0 {\n        n-=1\n        if n =? 2 {p.remove(a);}\n    }\n    printl(p[a])\n}\n', 9),
    'while_adds': ('main=(argv:array<string>):>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    let n=argv.length\n    let last=a\n    loop n >? 0 {\n        n-=1\n        p.remove(last);\n        last=p.add(n)\n    }\n    printl(p[a])\n}\n', 11),
    'mutating_call': ('drop=(@p:Pool<int64> h:Handle):>void=>{p.remove(h);}\nmain=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    drop(@p a)\n    printl(p[a])\n}\n', 6),
    'closure': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    let gone=($capture @p)=>{p.remove(a);}\n    gone()\n    printl(p[a])\n}\n', 6),
    # (a fact about one iteration's handle does not reach the next)
    'loop_order': ('f=(p:Pool<int64> hs:array<Handle>):>int64=>{\n    let t=0\n    loop h in hs {\n        t=p[h]\n        if not p.has(h) return 0\n    }\n    return t\n}\nmain=():>void=>printl(f([] []))\n', 4),
    # (the slot tables are the memberships)
    'private_write': ('main=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(1)\n    if p.__where.length >? 0 p.__where[0]=-1\n    printl(p[a])\n}\n', 5),
}


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text(source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_membership_proven(compiler, tmp_path):
    result = run(compiler, tmp_path, PROVEN, 'run')
    assert result.returncode == 0, result.stderr
    assert result.stdout == '39 scout 50 false\n7 none\n899 guard\n', result.stdout


@pytest.mark.parametrize('name', sorted(REJECTED))
def test_membership_unproven(compiler, tmp_path, name):
    source, line = REJECTED[name]
    result = run(compiler, tmp_path, source, 'check')
    assert result.returncode != 0
    errors = [text for text in result.stderr.splitlines() if ': error: ' in text]
    assert errors and errors[0].startswith(f'program.dewy:{line}:'), result.stderr
    assert 'the handle is' in errors[0] and 'in the pool' in errors[0], result.stderr


def test_membership_runtime_check(compiler, tmp_path):
    source = '$runtime_checks\nf=(p:Pool<int64> h:Handle):>int64=>p[h]\nmain=():>void=>{\n    let p:Pool<int64>=[]\n    let a=p.add(5)\n    printl(f(p a))\n    p.remove(a);\n    printl(f(p a))\n}\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 101 and result.stdout == '5\n', result.stdout + result.stderr
    assert 'gone from the pool' in result.stderr, result.stderr


def test_slot_tables_ignore_public_fields(compiler, tmp_path):
    # (`handles` is public: a clear or remove after it changed still gives
    # each slot once, so later handles stay distinct and others stay in)
    source = '''$runtime_checks
main=():>void=>{
    let p:Pool<int64>=[]
    let a=p.add(1)
    let b=p.add(2)
    p.handles[1]=a
    p.clear()
    let c=p.add(3)
    let d=p.add(4)
    printl"{p.has(c)} {p.has(d)} {p.has(a)}"
    let q:Pool<int64>=[]
    let x=q.add(1)
    let y=q.add(2)
    let z=q.add(3)
    q.handles[2]=x
    q.remove(y);
    printl"{q.has(x)} {q.has(y)} {q.has(z)}"
}
'''
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == 'true true false\ntrue false true\n', result.stdout + result.stderr
