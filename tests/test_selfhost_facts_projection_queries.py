"""Projection queries (key lookup, first and next records of a base, value origins) agree with frozen Jo
on small scanned states and on states past FACT_PROJECTION_SCAN whose projections are indexed."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

GLOBS = ('facts/*field*.dewy', 'facts/*record*.dewy', 'facts/*length*.dewy', 'refine_proven_rows/*.dewy',
         'refine_length_helpers/*.dewy', 'dict_refine/*.dewy', 'queue_refined_slots/*.dewy', 'heap_count/*.dewy')


def record_program(n):
    fields = ' '.join(f'f{i}:int64' for i in range(n))
    checks = ' and '.join(f'r.f{i} >=? 0 and r.f{i} <? xs.length' for i in range(n))
    total = ' + '.join(f'xs[r.f{i}]' for i in range(0, n, 7))
    values = ' '.join(str(i % 10) for i in range(n))
    return f'''$runtime_checks

R:type=[{fields}]
pick=(xs:array<int64> r:R):>int64=>{{
    if {checks} {{return {total}}}
    0
}}
lens=(a:array<int64> b:array<int64> c:array<int64> i:int64):>int64=>{{
    if i <? a.length and i <? b.length and i <? c.length and i >=? 0 {{return a[i] + b[i] + c[i]}}
    0
}}
main=()=>{{
    let xs:array<int64>=[1 2 3 4 5 6 7 8 9 10]
    printl(pick(xs R[{values}]) lens(xs xs xs 3))
}}
'''


def test_facts_projection_queries_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5] for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (4, 31, 40, 64):
        (tmp_path / f'records{n}.dewy').write_text(record_program(n))
        cases.append(str(tmp_path / f'records{n}'))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) > 20
