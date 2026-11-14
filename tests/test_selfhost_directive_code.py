"""Code-policy vectors (slots, masks, instance vectors, trap rules, pinned rows, requested bodies,
contexts and the foreign, parameter and generic numerics warnings) agree with frozen Jo: messages, IR,
bytes."""
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_directive_rules import MIXED

GENERIC = '''total_of=<T>(xs:array<T>):>T=>{
    let total:T=0
    loop x in xs {total+=x}
    total
}
pick=(xs:array<int64> i:int64):>int64=>{
    $runtime_assert i >=? 0 and i <? xs.length
    xs[i]
}
twice=(f:<(x:float64):>float64> v:float64):>float64=>f(f(v))
loose=(xs:array<int64> i:int64):>int64=>{
    $runtime_checks
    let g=(j:int64):>int64=>xs[j]
    g(i) + pick(xs i)
}
careful=(xs:array<float64>):>float64=>{
    $fast_math
    total_of(xs) + twice((x:float64):>float64=>x * 2.0 1.5)
}
proto=(xs:array<int64> i:int64):>int64=>{
    $prototype
    xs[i] + pick(xs i)
}
main=()=>{
    printl(loose([1 2 3] 1) proto([4 5 6] 2) careful([0.5 0.25]))
    printl(total_of([1 2 3]))
}
'''


def test_directive_code_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    # (one emitter: parallel workers interleave a large program's --ir text)
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    (tmp_path / 'mixed.dewy').write_text(MIXED)
    (tmp_path / 'vectors.dewy').write_text(GENERIC)
    globs = ('directives/*.dewy', 'notraps11/*.dewy', 'checked_index/*.dewy', 'metatag_prefix/*.dewy',
             'rational_float_bounds/*.dewy', 'float_constants/*.dewy', 'float_guards/*.dewy')
    files = [p for g in globs for p in sorted((ROOT / 'tests/cases').glob(g))]
    paths = ['mixed.dewy', 'vectors.dewy', 'tests/ladder/99_dewy_frontend/design.dewy'] + \
        [str(p.relative_to(ROOT)) for p in files]
    results = compare_builds(compiler, tmp_path, monkeypatch, ('directive_code',), paths,
                             flags=((), ('--release',), ('--ir',)))
    assert sum(r[2] == 0 for r in results) > 40 and any(r[2] != 0 for r in results)
    assert any('warning' in r[4] for r in results)
