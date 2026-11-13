"""Exact store chains (affine preimage checks, flag-checked trees with one cold exact path, combined offset stores) agree with
frozen Jo: the same messages, IR and bytes for the exact-int and bigint cases and near misses."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PROGRAM = '''$runtime_checks

chain=(a:int64 b:int64 c:int64):>int64=>a*b+c
chain3=(a:int64 b:int64 c:int64):>int64=>a*b-c*a+b
chain_small=(a:int64 b:int64):>int64=>a+b
chain_deep=(a:int64 b:int64):>int64=>a*b+a*b+a*b+a*b+a*b+a*b+a*b+a*b+a
chain_index=(xs:array<int64> i:int64 c:int64):>int64=>{
    if i <? 0 or i >=? xs.length return 0
    xs[i]*c-c
}
offset=(x:int64 y:int64):>int64=>{
    if y <? 0 or y >? 1000 return 0
    (x+5)+y
}
offset_minus=(x:int64 y:int64):>int64=>{
    if y <? 0 or y >? 1000 return 0
    (x-5)-y
}
offset_unbounded=(x:int64 y:int64):>int64=>(x+5)+y
offset_mixed=(x:int64 y:int64):>int64=>{
    if y <? 0 or y >? 1000 return 0
    (x+5)-y
}
affine=(x:int64):>int64=>3*x+7
affine_minus=(x:int64):>int64=>5*x-9
affine_right=(x:int64):>int64=>x*7+(-3)
affine_big=(x:int64):>int64=>2147483647*x+2147483647
affine_wide=(x:int64):>int64=>3*x+2147483648
affine_bounded=(x:int64):>int64=>{
    if x <? -10 or x >? 10 return 0
    1000*x-1
}
affine_low=(x:int64):>int64=>{
    if x <? 0 return 0
    4*x+1
}
affine_high=(x:int64):>int64=>{
    if x >? 0 return 0
    4*x-1
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    printl(chain(a b 3) chain3(a b 2) chain_small(a 1) chain_deep(a b) chain_index([a b] 1 a))
    printl(offset(a b) offset_minus(a b) offset_unbounded(a b) offset_mixed(a b) affine(a))
    printl(affine_minus(a) affine_right(a) affine_big(a) affine_wide(a) affine_bounded(a) affine_low(a) affine_high(a))
}
'''


def test_exact_chain_walks_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / 'chains.dewy').write_text(PROGRAM)
    files = [p for g in ('exact_int/*.dewy', 'bigint/*.dewy') for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = ['chains.dewy'] + [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_chain_walks',), paths,
                             flags=((), ('--release',)))
    assert results[0][2] == 0 and sum(r[2] == 0 for r in results) > 80
    (tmp_path / 'ir').mkdir()
    (tmp_path / 'ir/chains.dewy').write_text(PROGRAM)
    ir = compare_builds(compiler, tmp_path / 'ir', monkeypatch, ('exact_chain_walks',), ['chains.dewy'],
                        flags=(('--ir',), ('--ir', '--release')))
    assert all(r[2] == 0 and 'overflow_mul' in r[3] for r in ir)
