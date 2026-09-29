"""Immutable startup owners can supply stable call-root fields."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute
from test_record_argument_loans import SOURCE

GLOBAL = SOURCE.replace('forward=(items:array<int64>):>int64 & no_effects=>read(Pair[items 40])',
    'const fixed:array<int64>=[20 22]\nforward=(items:array<int64>):>int64 & no allocates=>read(Pair[fixed 40])')
CASES = [GLOBAL, GLOBAL.replace('const fixed:array<int64>=[20 22]',
    'Box:type=[items:array<int64>]\nconst fixed=Box[[20 22]]').replace('Pair[fixed 40]', 'Pair[fixed.items 40]')]
CASES.append(GLOBAL.replace('pair.items.length+pair.offset',
    'if pair.items.length=?2 pair.items[0]+pair.items[1] else 0'))
FACTORY = GLOBAL.replace('const fixed:array<int64>=[20 22]',
    'make=():>array<int64>=>[20 22]\nconst fixed=make()')
SNAPSHOT = GLOBAL.replace('const fixed:array<int64>=[20 22]',
    'let mutable:array<int64>=[20 22]\nconst fixed:array<int64>=mutable.copy()')
CASES += [FACTORY, SNAPSHOT,
    SNAPSHOT.replace('pair.items.length+pair.offset',
        'if pair.items.length=?2 pair.items[0]+pair.items[1] else 0')
        .replace('main=():>int64=>work([20 22])', 'main=():>int64=>{mutable.clear() return work([20 22])}'),
    GLOBAL.replace('const fixed:array<int64>=[20 22]',
        'Box:type=[items:array<int64>]\nmake=():>Box=>Box[[20 22]]\nconst fixed=make()')
        .replace('Pair[fixed 40]', 'Pair[fixed.items 40]'),
]
ERRORS = [GLOBAL.replace('const fixed:', 'let fixed:'),
    FACTORY.replace('const fixed=', 'let fixed='),
    # The startup initializer rule must not admit captured local owners.
    FACTORY.replace('const fixed=make()\nforward=', 'forward=').replace(
        '=>read(Pair[fixed 40])',
        '=>{let fixed=make()\nchange=():>void=>{fixed.clear();}\nchange()\nreturn read(Pair[fixed 40])}'),
]

@pytest.mark.parametrize('source', CASES)
def test_constant_argument_loans(tmp_path, source):
    execute(tmp_path, 'constant-root', codegen(SrcFile(None, source), debug_locations=False))

@pytest.mark.parametrize('source', ERRORS)
def test_unknown_global_storage_keeps_its_obligation(source):
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, source), debug_locations=False)


def test_factory_owner_requires_independence_proof(monkeypatch):
    from dewy.semantic.analyze import storage_borrows
    monkeypatch.setattr(storage_borrows, 'private_origin', lambda node: False)
    with pytest.raises(ReportException, match='effect contract|unproven copy'):
        codegen(SrcFile(None, FACTORY), debug_locations=False)


def test_native_constant_argument_loans(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)
