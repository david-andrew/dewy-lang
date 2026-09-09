"""Address facts use the evaluated value and the inclusive target maximum."""

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze import bounds
from dewy.semantic.errors import UserError
from dewy.targets import ADDRESS_BITS, max_length


def test_converted_lookup_keeps_its_interval_when_proving_an_address():
    codegen(SrcFile(None, '''
const widths:totaldict<'small'|'large' uint8> = ['small' -> 32 'large' -> 48]
let width = (name:'small'|'large'):>addr => widths[name]
let main = ():>int64 => width('large')
'''))


@pytest.mark.parametrize('target', ADDRESS_BITS)
def test_address_contract_includes_the_last_address(target):
    loc = Span(0, 0)
    registry = bindings.BindingRegistry()
    root = hir.Block(loc, 'void', [], False)
    validator = bounds._BoundsValidator(registry, SrcFile(None, ''), root, target)
    expected = bounds.Interval(0, (1 << ADDRESS_BITS[target]) - 1, capped=True)
    assert validator._bounds_of(ty.addr_type().propositions) == expected
    # A value exactly at the inclusive maximum still proves the upper axiom.
    value = hir.Integer(loc, 'int64', '0d', max_length(target))
    assert validator._proposition_verdict(ty.ADDR_PROPOSITION, value, bounds.Interval.exact(max_length(target)), {}) is True
    assert validator._proposition_verdict(ty.ADDR_PROPOSITION, value, None, {}) is True


def test_an_address_still_needs_a_nonnegative_value():
    with pytest.raises(UserError):
        codegen(SrcFile(None, 'let f = (n:int8):>addr => n'))


def test_an_address_still_needs_a_bounded_value():
    with pytest.raises(UserError):
        codegen(SrcFile(None, 'let f = (n:uint64):>addr => n'))
