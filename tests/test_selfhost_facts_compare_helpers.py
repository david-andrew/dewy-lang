"""Saved-Boolean recognition and signed overflow guards match Jo."""
import pytest
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_facts_double import compare_facts
from tests.selfhost_lower_double import modules_for
from tests.support import ROOT, compiler  # noqa: F401

LEAF = ('facts_compare',)
DRIVER = '''use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'checker_types.dewy'
use 'checker_tokens.dewy'
use 'types.jo'
use 'type_ops.dewy'
use 'facts.jo'
use 'refinement_types.dewy'
use 'util.jo'
fail = (code: int):
    print("assertion {code}")
    exit(code)
main = ():
    init_types()
    # Independent sign-bit addition overflow oracle, including both endpoints.
    values = [FACT_MIN, FACT_MIN + 1, -(1 << 62), -2147483648, -1, 0, 1, 2147483647, 1 << 62, FACT_MAX - 1, FACT_MAX]
    loop a in values:
        loop b in values:
            r = a + b
            if fact_add_fits(a, b) != (((a xor r) & (b xor r)) >= 0): fail(12)
    a = FACT_MIN; b = FACT_MAX
    loop i in [0..2048):
        a = a * 6364136223846793005 + 1442695040888963407
        b = b * 2862933555777941757 + 3037000493
        r = a + b
        if fact_add_fits(a, b) != (((a xor r) & (b xor r)) >= 0): fail(13)
    nodes = fill(Node(), 128)
    nodes[1] = Node(kind=.and_); nodes[2] = Node(kind=.or_)
    nodes[3] = Node(kind=.ident)
    nodes[4] = Node(kind=.not_, a=1); nodes[5] = Node(kind=.not_, a=4)
    nodes[6] = Node(kind=.not_, a=3); nodes[7] = Node(kind=.not_, a=0)
    nodes[8] = Node(kind=.conv, a=1)
    if not fact_saved_boolean(1) or not fact_saved_boolean(2) or not fact_saved_boolean(5): fail(20)
    if fact_saved_boolean(-1) or fact_saved_boolean(0) or fact_saved_boolean(6) or fact_saved_boolean(7) or fact_saved_boolean(8): fail(21)
    loop i in [9..100): nodes[i] = Node(kind=.not_, a=i32(if i == 9: 2 else: i - 1))
    held_nodes = nodes
    if not fact_saved_boolean(99): fail(22)
    nodes[2].kind = .ident
    if fact_saved_boolean(99) or held_nodes[2].kind != .or_: fail(23)
    print("comparison helpers ok")
'''

@pytest.mark.parametrize('release', [False, True])
def test_facts_compare_helpers_twins(compiler, tmp_path, release):
    modules = modules_for(ROOT / 'compiler/main.jo', tmp_path / 'unused', LEAF)
    compare_leaf(compiler, tmp_path, release, DRIVER, extra_stems=LEAF, jo_doubles=modules)


def test_facts_compare_helpers_program_twins(compiler, tmp_path, monkeypatch):
    globs = ('saved_operands/*.dewy', 'facts/comparison.dewy', 'facts/short_circuit.dewy',
             'facts/endpoint*.dewy', 'facts/bounded_sum*.dewy', 'facts/wrap_unknown.dewy',
             'facts/plain_binding_guards.dewy', 'directives/runtime_index_values.dewy')
    cases = sorted({str(p.relative_to(ROOT / 'tests/cases'))[:-5]
                    for glob in globs for p in (ROOT / 'tests/cases').glob(glob)})
    assert compare_facts(compiler, tmp_path, monkeypatch, cases, leaves=LEAF) >= 10
