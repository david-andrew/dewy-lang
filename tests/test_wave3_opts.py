"""Correctness and edge-case tests for Wave 3 runtime optimizations:
- last-use move RC elimination on loop-tail `arr.push(local)`
- single-probe `if d.get(k) is? none { d[k] = v; ... }` / `if not d.has(k) { d[k] = v; ... }`
- overflow-free exact comparison `x + c cmp z` (including int64 extremes)
- `ib_offs` / `ib_early_exit_if` bounds proof soundness (valid and panicking OOB)
- `o_licm_release` non-escaping local struct-field load hoisting
"""
import subprocess

import pytest

from tests.support import compiler


def _build_and_run(compiler, tmp_path, name, source, *, release=False):
    src = tmp_path / f'{name}_{"rel" if release else "dbg"}.dewy'
    exe = tmp_path / f'{name}_{"rel" if release else "dbg"}'
    src.write_text(source)
    flags = ['--release'] if release else []
    built = subprocess.run([compiler, 'build', src, '-o', exe, *flags],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    return subprocess.run([exe], capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize('release', [False, True])
def test_push_last_use_move_edges(compiler, tmp_path, release):
    source = r'''
$runtime_checks

main = ():>void => {
    # Normal loop-tail push of a fresh managed local.
    let rows:array<array<int64>>=[]
    loop i in [0..10) {
        let row:array<int64>=[i i * 2]
        rows.push(row)
    }

    # Early continue / break before the tail push must still clean up skipped locals.
    let kept:array<array<int64>>=[]
    loop i in [0..10) {
        let row:array<int64>=[i i + 100]
        if i % 2 =? 0 { continue }
        if i >? 7 { break }
        kept.push(row)
    }

    # Non-tail push followed by a read of the local must NOT consume it early.
    let read_after_len:int64=0
    let non_tail:array<array<int64>>=[]
    loop i in [0..4) {
        let row:array<int64>=[i i + 1 i + 2]
        non_tail.push(row)
        read_after_len += row.length
    }

    # Shared local aliased into a second array before tail push.
    let a:array<array<int64>>=[]
    let b:array<array<int64>>=[]
    loop i in [0..4) {
        let row:array<int64>=[i * 10]
        a.push(row)
        b.push(row)
    }
    b[0][0]=999

    print("{rows.length} {rows[9][1]} {kept.length} {kept[3][1]} {read_after_len} {non_tail.length} {a[0][0]} {b[0][0]}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'push_move', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == '10 18 4 107 12 4 0 999'


@pytest.mark.parametrize('release', [False, True])
def test_map_insert_if_absent_semantics(compiler, tmp_path, release):
    source = r'''
$runtime_checks

side_effect_val = (@calls:int64 x:int64):>int64 => {
    calls += 1
    x * 10
}

main = ():>void => {
    let m:dict<int64 int64>=[]
    let calls:int64=0
    let hits:int64=0
    let misses:int64=0
    let keys:array<int64>=[1 2 1 3 2 1 4]
    loop k in keys {
        if m.get(k) is? none {
            m[k]=side_effect_val(@calls k)
            misses += 1
        } else {
            hits += 1
        }
    }
    # Second pattern: `if not d.has(k)` with value expression that would divide by zero if evaluated when present.
    let m2:dict<int64 int64>=[]
    m2[10]=77
    let zero:int64=0
    let k10:int64=10
    if not m2.has(k10) {
        m2[k10]=1 // zero
    }
    let k20:int64=20
    if not m2.has(k20) {
        m2[k20]=88
    }
    # Value expression referencing the map itself must fall back safely (not miscompile).
    let m3:dict<int64 int64>=[]
    m3[1]=5
    let k2:int64=2
    if m3.get(k2) is? none {
        m3[k2]=m3.length + 100
    }
    print("{m.length} {calls} {misses} {hits} {m.get(3) ?? -1} {m2.get(10) ?? -1} {m2.get(20) ?? -1} {m3.get(2) ?? -1}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'map_insert', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == '4 4 4 3 30 77 88 101'


@pytest.mark.parametrize('release', [False, True])
def test_exact_add_compare_extremes(compiler, tmp_path, release):
    source = r'''
$runtime_checks

check = (x:int64 z:int64):>int64 => {
    let out:int64=0
    if z >=? 0 {
        if x + 3 <=? z { out += 1 }
        if x + 3 <? z { out += 2 }
        if 3 + x >=? z { out += 4 }
        if x + 9223372036854775807 >? z { out += 8 }
    }
    out
}

main = ():>void => {
    let max64:int64=9223372036854775807
    let min64:int64=-9223372036854775807 - 1
    # x = max64, z = max64 -> x + 3 > z (must NOT wrap around and claim <= z!)
    let a=check(max64 max64)
    # x = max64 - 3, z = max64 -> x + 3 == z -> <= (1), >= (4), +max64 > z (8) => 13
    let b=check(max64 - 3 max64)
    # x = min64, z = 0 -> min64 + 3 < 0 -> <= (1), < (2), min64 + max64 = -1 <= 0 (0) => 3
    let c=check(min64 0)
    # x = 0, z = 0 -> 3 > 0 -> >= (4), +max64 > 0 (8) => 12
    let d=check(0 0)
    print("{a} {b} {c} {d}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'exact_cmp', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == '12 13 3 12'


@pytest.mark.parametrize('release', [False, True])
def test_ib_early_exit_and_licm_slot_load(compiler, tmp_path, release):
    source = r'''
$runtime_checks

Node:type=[priority:int64 val:int64]

sift = (@h:array<Node>):>int64 => {
    let last=h.pop()
    let n:int64=h.length
    if n =? 0 { return last.val }
    let i:int64=0
    loop true {
        let left:int64=i * 2 + 1
        if left >=? n { break }
        let right:int64=left + 1
        let best:int64=left
        if right <? n and h[right].priority <? h[left].priority { best=right }
        if last.priority <=? h[best].priority { break }
        h[i]=h[best]
        i=best
    }
    h[i]=last
    h[0].priority * 100 + h[n - 1].priority
}

# Slot-load LICM must NOT hoist a field when the struct is mutated inside the loop.
mutated_slot = (limit:int64):>int64 => {
    let cur=Node[1 0]
    let acc:int64=0
    let i:int64=0
    loop i <? limit {
        acc += cur.priority
        if i =? 2 { cur.priority=10 }
        i += 1
    }
    acc
}

main = ():>void => {
    let h:array<Node>=[Node[1 10] Node[4 40] Node[2 20] Node[8 80] Node[5 50]]
    let r1=sift(@h)
    let r2=mutated_slot(5)
    print("{r1} {r2}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'ib_licm', source, release=release)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip() == '208 23'


@pytest.mark.parametrize('release', [False, True])
def test_ib_offset_still_catches_oob(compiler, tmp_path, release):
    source = r'''
$runtime_checks

bad = (a:array<int64>):>int64 => {
    let n:int64=a.length
    let i:int64=0
    let s:int64=0
    loop i <? n {
        # i + 2 <= n only proves a[i] and a[i + 1], NOT a[i + 2].
        if i + 2 <=? n {
            s += a[i + 2]
        }
        i += 1
    }
    s
}

main = ():>void => {
    let a:array<int64>=[1 2 3 4]
    print("{bad(a)}")
}
'''
    ran = _build_and_run(compiler, tmp_path, 'ib_oob', source, release=release)
    assert ran.returncode != 0
