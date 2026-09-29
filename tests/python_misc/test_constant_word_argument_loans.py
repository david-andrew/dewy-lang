"""Erasing an obligation must preserve a closed constant's storage proof."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from dewy.semantic.analyze.storage_borrows import independent_materialization, private_origin
from test_scalar_projection import execute


SOURCE = (Path(__file__).resolve().parents[1] / 'fixtures/record_argument_loans.dewy').read_text()
SOURCE = SOURCE.replace('Pair:type=', 'const OFFSET:addr=40\nPair:type=')
SOURCE = SOURCE.replace('pair.items.length+pair.offset', 'pair.items.length+OFFSET')
CASES = [SOURCE,
    SOURCE.replace('OFFSET:addr=40', 'OFFSET:int64=40'),
    SOURCE.replace('OFFSET:addr=40', 'OFFSET:addr={40}'),
    SOURCE.replace('OFFSET:addr=40', 'OFFSET:addr=20+20'),
]


@pytest.mark.parametrize('source', CASES)
def test_constant_word_argument_loans(tmp_path, source):
    execute(tmp_path, 'constant-word-loan', codegen(SrcFile(None, source), debug_locations=False))


def test_closed_block_requires_every_child_to_be_independent():
    loc = Span(0, 1)
    value = hir.Integer(loc, ty.IntegerLiteralType(40), '0d', 40)
    assert independent_materialization(hir.Block(loc, value.type, [hir.Void(loc, 'void'), value], False))
    for read in [hir.ExpressedIdentifier(loc, 'int64', 'ambient'),
                 hir.FunctionCall(loc, 'int64', hir.ExpressedIdentifier(
                     loc, ty.FunctionType([], [], None, 'int64'), 'unknown'), [], {})]:
        assert not independent_materialization(hir.Block(loc, value.type, [read, value], False))


def test_only_erased_witnesses_preserve_private_result_provenance():
    loc = Span(0, 1)
    call = hir.FunctionCall(loc, 'int64', hir.ExpressedIdentifier(
        loc, ty.FunctionType([], [], None, 'int64'), 'make'), [], {})
    assert private_origin(hir.Block(loc, call.type, [hir.Void(loc, 'void'), call], False))
    assert not private_origin(hir.Block(loc, call.type, [call, call], False))
    assert private_origin(hir.Obligation(loc, call.type, call, ty.RefinedType('int64', ()), 'return promise'))


def test_native_constant_word_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])
