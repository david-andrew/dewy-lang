"""Selecting a node rule must not cache facts or skip side effects."""
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir
from dewy.semantic.analyze.bounds import Interval, _BoundsValidator


class IdentifierSubclass(hir.ExpressedIdentifier):
    pass


def test_inherited_node_rule_reads_current_state_and_place_forgets_it():
    loc = Span(0, 0)
    root = hir.Block(loc, 'void', [], scoped=False)
    validator = _BoundsValidator(bindings.BindingRegistry(), SrcFile(None, ''), root)
    node = IdentifierSubclass(loc, 'int64', 'n', binding_id=17)
    state = {17: Interval.exact(3)}
    assert validator._eval(node, state, validate=False) == Interval.exact(3)
    state[17] = Interval.exact(-1)
    assert validator._eval(node, state, validate=True) == Interval.exact(-1)
    place = hir.Place(loc, 'int64', node)
    validator._eval(place, state, validate=False)
    assert 17 not in state
    assert validator._eval(node, state, validate=False) == Interval(-(1 << 63), (1 << 63) - 1)
