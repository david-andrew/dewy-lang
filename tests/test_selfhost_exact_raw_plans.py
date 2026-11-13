"""Exact raw-word representation plans (local widths over plain writes, expression bit plans, raw
consumer marking for declarations, assignments, comparisons and conversions) agree with frozen Jo."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PROGRAM = '''$runtime_checks

locals_=(a:int64 b:int64):>int64=>{
    let x:int=a*b
    let y:int=x+a
    let z:int=-(x-b)
    y=y*2-x
    let w:int=if a >? b {x} else {z}
    let v:int=x*x*x*x*x
    if x <? y and z >=? w {return int64((x+y) % 1000)}
    int64((y+z+w) % 999) + int64(v % 7)
}
masks=(a:uint64 b:int64):>int64=>{
    let x:int=a & 255
    let y:int=(x | b) ^ 3
    let c:int=18446744073709551615
    int64((y + x * 2) % 100) + int64(c % 5)
}
grow=(n:int64):>int64=>{
    let x:int=1
    loop i in [0..n) {x=x*3}
    int64(x % 1000)
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    printl(locals_(a b) masks(uint64(5) b) grow(a % 50))
}
'''


def test_exact_raw_plans_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / 'plans.dewy').write_text(PROGRAM)
    globs = ('exact_int/*.dewy', 'bigint/*.dewy', 'numeric/*.dewy', 'effects/*.dewy')
    files = [p for g in globs for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = ['plans.dewy'] + [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_raw_plans',), paths,
                             flags=((), ('--release',), ('--ir',)))
    assert results[0][2] == 0 and sum(r[2] == 0 for r in results) > 200
