"""Difference proofs close finite chains without assuming new evidence."""

import pytest

from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, check, hir
from dewy.semantic.analyze import bounds as b
from dewy.semantic.errors import UserError


GUARD = 'a <=? b and b <=? c and c <=? d and d <=? e and e <=? f and f <=? g and g <=? h'
HEADER = 'ordered = (a:int64 b:int64 c:int64 d:int64 e:int64 f:int64 g:int64 h:int64):>int64 => {\n'
CASES = [HEADER + f'if {GUARD} {{$assert a <=? h return 42}} return 0\n}}\nmain=():>int64=>ordered(1 2 3 4 5 6 7 8)',
         HEADER.replace('h:int64)', 'h:int64 xs:array<int64>)') + f'if 0 <=? a and {GUARD} and h <? xs.length {{return xs[a]}} return 0\n}}\nmain=():>int64=>ordered(0 1 2 3 4 5 6 7 [42 0 0 0 0 0 0 0])']
CASES.append(HEADER + f'if 0 <=? a and {GUARD} {{let width:uint64=h-a return if width =? 7 42 else 0}} return 0\n}}\nmain=():>int64=>ordered(1 2 3 4 5 6 7 8)')

ERRORS = [HEADER + f'if {GUARD.replace("d <=? e", "true")} {{$assert a <=? h}} return 0\n}}',
          HEADER + f'if {GUARD} {{d=0 $assert a <=? h}} return 0\n}}',
          HEADER + f'if {GUARD} {{$unsafe_assume h <? a}} return 0\n}}']


@pytest.mark.parametrize('source', CASES)
def test_long_chain_is_proven(source):
    check.typecheck_and_resolve(SrcFile(None, source))


@pytest.mark.parametrize('source', ERRORS)
def test_missing_invalidated_or_contradictory_chain_is_rejected(source):
    with pytest.raises(UserError):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_weighted_paths_and_cycles():
    span = Span(0, 0)
    validator = b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(span, 'void', [], True))
    state = {b._order_key(i, i + 1): b.Interval(1, None) for i in range(1, 12)}
    assert validator._ordered(1, 12, 11, state)
    assert not validator._ordered(1, 12, 12, state)
    # A weak early path must not suppress a stronger later path to the same term.
    state[b._order_key(1, 8)] = b.Interval(-10, None)
    state[b._order_key(8, 2)] = b.Interval(-6, None)
    assert validator._ordered(1, 12, 11, state)
    assert not validator._ordered(1, 12, 12, state)
    # Unreachable destinations stay unknown even with a contradictory cycle.
    state[b._order_key(8, 2)] = b.Interval(1, None)
    assert not validator._ordered(1, 99, 0, state)


def test_difference_bounds_retain_cap_provenance():
    span = Span(0, 0)
    validator = b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(span, 'void', [], True))
    state = {b._order_key(1, 2): b.Interval(2, None, capped=True),
             b._order_key(2, 3): b.Interval(-1, None),
             b._order_key(1, 3): b.Interval(0, None)}
    result = validator._order_search(1, 3, state)
    assert result.lower == 1 and result.capped
    state[b._order_key(1, 4)] = b.Interval(3, None)
    state[b._order_key(4, 3)] = b.Interval(-2, None)
    result = validator._order_search(1, 3, state)
    assert result.lower == 1 and not result.capped
    assert validator._order_search(1, 99, state) is None


def test_difference_search_matches_simple_path_oracle():
    """Small consistent graphs exercise diamonds, negative edges and cycles."""
    import random

    randomizer = random.Random(7321)
    span = Span(0, 0)
    validator = b._BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), hir.Block(span, 'void', [], True))
    for _ in range(40):
        values = [randomizer.randrange(-20, 21) for _ in range(6)]
        edges = {(a, c): values[c] - values[a] - randomizer.randrange(4)
                 for a in range(6) for c in range(6) if a != c and randomizer.random() < .25}
        state = {b._order_key(a, c): b.Interval(weight, None) for (a, c), weight in edges.items()}
        for source in range(6):
            # Enumerate simple paths independently of the worklist. Generating
            # edges below concrete value differences excludes positive cycles.
            expected = {source: 0}
            def visit(node, distance, seen):
                for (left, right), weight in edges.items():
                    if left != node or right in seen:
                        continue
                    total = distance + weight
                    expected[right] = max(expected.get(right, total), total)
                    visit(right, total, seen | {right})
            visit(source, 0, {source})
            for target in range(6):
                actual = validator._order_search(source, target, state)
                assert (None if actual is None else actual.lower) == expected.get(target)
