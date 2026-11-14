"""Difference-row queries (row lookup, incidence, chain heads and successors, ordered scans) agree with
frozen Jo on small scanned states and on states past FACT_ROW_SCAN whose rows are indexed."""
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

GLOBS = ('loop_bounds/*.dewy', 'saved_operands/*.dewy', 'dogfood35_proofs/*.dewy', 'product_bounds/*.dewy',
         'facts/nonlinear*.dewy', 'facts/relation*.dewy', 'facts/distance*.dewy', 'range/stepped_error_1*.dewy')


def chain_program(n):
    params = ' '.join(f'a{i}:int64' for i in range(n + 1))
    chain = ' and '.join(f'a{i} <=? a{i + 1}' for i in range(n))
    values = ' '.join(str(min(i // 5, 9)) for i in range(n + 1))
    return f'''$runtime_checks

chain=(xs:array<int64> {params}):>int64=>{{
    if a0 >=? 0 and a{n} <? xs.length and {chain} {{return xs[a{n // 2}] + xs[a0] + xs[a{n}]}}
    0
}}
short=(xs:array<int64> i:int64 j:int64 k:int64):>int64=>{{
    if 0 <=? i and i <=? j and j <=? k and k <? xs.length {{return xs[j] + xs[i]}}
    0
}}
main=()=>{{
    let xs:array<int64>=[1 2 3 4 5 6 7 8 9 10]
    printl(chain(xs {values}) short(xs 1 2 3))
}}
'''


def test_facts_row_queries_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    cases = [str(p.relative_to(ROOT / 'tests/cases'))[:-5] for g in GLOBS for p in sorted((ROOT / 'tests/cases').glob(g))]
    for n in (8, 31, 40, 70):
        (tmp_path / f'rows{n}.dewy').write_text(chain_program(n))
        cases.append(str(tmp_path / f'rows{n}'))
    assert compare_facts(compiler, tmp_path, monkeypatch, cases) > 20
