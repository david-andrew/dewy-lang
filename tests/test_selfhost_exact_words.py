"""Fixed-size exact words (extension, add/subtract with carries, comparisons, products, selects,
restoring division and literal/barrel shifts) agree with frozen Jo: the same messages, IR and bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

PROGRAM = '''
$runtime_checks

wide=(a:int64 b:int64 c:int64):>int64=>{
    let p:int=a*b
    let q=p // c
    let r=p % c
    let s=(p >> 7) + (p << 3)
    let t=if p >? q {p - q} else {q - p}
    let u=(a*b*c) // (b*c + 1)
    int64((q + r + (s >> 70) + t // 3 + u) % 1000000007)
}
cmp=(a:int64 b:int64):>bool=>a*b <? b*b and a*a not=? b*a and a*a >=? a*b and a*b <=? b*b
shift=(a:int64 k:int64):>int64=>{
    if k <? 0 or k >? 100 return 0
    let p:int=a*a
    int64(((p << k) >> k) % 1000003) + int64((p >> k) % 7)
}
main=(args:array<string>)=>{
    let a=int64(to_int(args[1]) ?? 0)
    let b=int64(to_int(args[2]) ?? 0)
    let c=int64(to_int(args[3]) ?? 1)
    printl(wide(a b c) cmp(a b) shift(a 5) shift(b 77))
}
'''


def test_exact_words_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / 'words.dewy').write_text(PROGRAM)
    globs = ('exact_int/*.dewy', 'bigint/*.dewy', 'numeric/*.dewy')
    files = [p for g in globs for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = ['words.dewy'] + [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_words',), paths, flags=((), ('--release',)))
    assert results[0][2] == 0 and sum(r[2] == 0 for r in results) > 150
    (tmp_path / 'ir').mkdir()
    (tmp_path / 'ir/words.dewy').write_text(PROGRAM)
    ir = compare_builds(compiler, tmp_path / 'ir', monkeypatch, ('exact_words',), ['words.dewy'],
                        flags=(('--ir',), ('--ir', '--release')))
    assert all(r[2] == 0 and 'divu' in r[3] for r in ir)
