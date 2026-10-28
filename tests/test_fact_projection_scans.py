"""Projection queries retain insertion order through promotion and branch copies."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def test_projection_queries_across_branch_promotion(compiler, tmp_path):
    source = tmp_path / 'projections.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / name}'\n" for name in
                              ('facts.jo', 'types.jo', 'refinement_types.dewy')) + '''
# Compare every query against the ordered records, including repeated keys
# whose first value wins and reverse lookups that exclude element records.
check = (s: FactState):
    loop i in [0..s.projections.len()):
        p = s.projections[i]
        first = -1
        next = -1
        key = -1
        origin = -1
        loop j in [0..s.projections.len()):
            q = s.projections[j]
            if q.base == p.base:
                if first < 0: first = j
                if j > i and next < 0: next = j
                if key < 0 and q.selector == p.selector and q.element == p.element: key = j
            if origin < 0 and not q.element and q.value == p.value: origin = j
        assert(fact_projection_find(s, p.base, p.selector, p.element) == key)
        assert(fact_projection_first(s, p.base) == first)
        assert(fact_projection_after(s, i) == next)
        assert(fact_projection_origin(s, p.value) == origin)
    assert(fact_projection_find(s, 999, 1, false) == -1)
    assert(fact_projection_first(s, 999) == -1)
    assert(fact_projection_origin(s, 999) == -1)

state = FactState()
check(state)
fact_add_projection(state, FactProjection(1, -1, false, 100))
fact_add_projection(state, FactProjection(2, -1, true, 100))
fact_add_projection(state, FactProjection(1, -1, false, 101))
fact_add_projection(state, FactProjection(1, -1, false, 100))
assert(state.projections.len() == 3)
loop i in [3..31): fact_add_projection(state, FactProjection(1 + i % 5, i, i % 3 == 0, 100 + i % 7))
check(state)
assert(not fact_projections_indexed(state))
left = state
right = state
records = state.projections
links = state.index[0].projection_next
fact_add_projection(left, FactProjection(1, 90, false, 190))
fact_add_projection(right, FactProjection(1, 91, false, 191))
assert(fact_projections_indexed(left) and fact_projections_indexed(right))
assert(not fact_projections_indexed(state))
check(state); check(left); check(right)
assert(fact_projection_find(left, 1, 91, false) == -1)
assert(fact_projection_find(right, 1, 90, false) == -1)
# Traversing saved records must ignore projections created by the write.
last = fact_projection_first(state, 1)
loop fact_projection_next_in(records, links, last) >= 0:
    last = fact_projection_next_in(records, links, last)
assert(fact_projection_after(left, last) == 31)
assert(fact_projection_next_in(records, links, last) == -1)
# Indexed siblings also keep independent tails and first-key identities.
indexed = left
fact_add_projection(left, FactProjection(1, 92, false, 192))
check(indexed); check(left)
assert(fact_projection_find(indexed, 1, 92, false) == -1)
assert(fact_projection_after(indexed, 31) == -1)
assert(fact_projection_after(left, 31) == 32)
# Rebuilding after collection preserves every ordered record and answer.
fact_reindex(left)
check(left)
fact_reindex(state)
check(state)
# Replacement starts from an unindexed snapshot and promotes while copying
# its sibling fields. New projections must not enter that saved traversal.
init_types()
fact_terms = [FactTerm()]
record = FactState()
base = fact_new(record, FactBound(), FactTerm(type = T_INT))
value = fact_new(record, FactBound(10, 10), FactTerm(type = T_INT))
replacement = fact_new(record, FactBound(20, 20), FactTerm(type = T_INT))
loop selector in [0..31): fact_add_projection(record, FactProjection(base, selector, false, value))
assert(not fact_projections_indexed(record))
fresh = fact_replace(record, base, 7, false, replacement, T_INT)
assert(fact_projections_indexed(record))
assert(record.projections.len() == 62)
loop selector in [0..31):
    before = fact_projection_find(record, base, selector, false)
    after = fact_projection_find(record, fresh, selector, false)
    assert(record.projections[before].value == value)
    assert(record.projections[after].value == (if selector == 7: replacement else: value))
check(record)
print("ok")
''')
    binary = tmp_path / 'projections'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == 'ok\n', ran.stdout + ran.stderr
