"""Shift-extent bounds (refined contracts, readonly globals, captured values, conversions, complement,
lengths, moduli and endpoint arithmetic in the indexed cache) agree with frozen Jo: messages, IR, bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PROGRAM = '''
$runtime_checks

LIMIT=40
Small:type=int64<(<? 50)>
SmallB:type=int64<(<? 20)>
SmallC:type=int64<(>? 3)>
shift_param=(x:int k:Small):>int64=>{
    if k <? 0 return 0
    int64((x << k) % 1000)
}
shift_b=(x:int k:SmallB):>int64=>{
    if k <? 0 return 0
    int64((x << k) % 1000)
}
shift_c=(x:int k:SmallC):>int64=>{
    if k >? 30 return 0
    int64((x << k) % 1000)
}
shift_global=(x:int):>int64=>int64((x << LIMIT) % 997)
shift_mask=(x:int k:int64):>int64=>int64((x << (k & 31)) % 991) + int64((x << (k % 17)) % 7)
shift_ops=(x:int a:int64 b:int64):>int64=>{
    let i=a & 15
    let j=b & 7
    let s=i + j
    let d=i - j
    let p=i * j
    let q=i // (j + 1)
    let r=i >> 2
    let t=~j & 3
    int64(((x << s) + (x << (d & 63)) + (x << p) + (x << q) + (x << r) + (x << t)) % 1009)
}
shift_len=(x:int xs:array<int64>):>int64=>int64((x << (xs.length % 60)) % 983)
captured=(x:int k:int64):>int64=>{
    let m=k & 7
    let f=(y:int):>int=>y << m
    int64(f(x) % 977)
}
main=(args:array<string>)=>{
    let x=to_int(args[1]) ?? 0
    let k=int64(to_int(args[2]) ?? 0)
    printl(shift_b(x 5) shift_c(x 9) shift_param(x 7) shift_global(x) shift_mask(x k) shift_ops(x k k + 3) shift_len(x [1 2 3]) captured(x k))
}
'''


def test_exact_count_bounds_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / 'counts.dewy').write_text(PROGRAM.lstrip())
    globs = ('exact_int/*.dewy', 'bigint/*.dewy', 'numeric/*.dewy', 'effects/*.dewy', 'refinements/*.dewy',
             'limb_bounds/*.dewy', 'product_bounds/*.dewy', 'loop_bounds/*.dewy')
    files = [p for g in globs for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = ['counts.dewy'] + [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_count_bounds',), paths,
                             flags=((), ('--release',), ('--ir',)))
    assert results[0][2] == 0 and sum(r[2] == 0 for r in results) > 200
