"""Runtime fact procedures stay distinct from erased proof statements."""
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile, ReportException
from dewy.semantic.errors import UserError
from tests.python_misc.test_scalar_projection import execute


def test_runtime_fact_procedure_keeps_its_write(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/runtime_fact_procedure.dewy'
    execute(tmp_path, 'runtime-fact-procedure', codegen(SrcFile.from_path(fixture)))


@pytest.mark.parametrize('body', ['return', 'if xs.length =? 0 return', 'if xs.length >? 0 return'])
def test_runtime_fact_procedure_checks_every_exit(body):
    with pytest.raises(UserError, match='refinement'):
        codegen(SrcFile(None, f'ensure=(@xs:array<int64>):> void & <xs.length >? 0> => {{ {body} }}'))


POSITIVE = '$proof\npositive=(x:int64<v=>v>?0>):> <x>?0> => {$assert x>?0}\n'


def test_proof_definition_and_call_erase(tmp_path):
    emitted = codegen(SrcFile(None, POSITIVE + 'main=():>int64=>{positive(42) return 42}'))
    assert 'positive' not in emitted
    execute(tmp_path, 'erased-proof', emitted)


@pytest.mark.parametrize('use', [
    'let x=positive(42)', 'let callback=@positive',
    'let callback=positive', 'return positive(42)',
])
def test_proof_is_not_a_value(use):
    with pytest.raises(ReportException):
        codegen(SrcFile(None, POSITIVE + f'main=():>int64=>{{{use}\nreturn 42}}'))


@pytest.mark.parametrize('body', ['printl("effect")', 'loop true {}', 'positive(x)'])
def test_effect_divergence_and_recursion_do_not_prove(body):
    with pytest.raises(UserError):
        codegen(SrcFile(None, '$proof\npositive=(x:int64):> <x>?0> => {' + body + '}'))


def test_proof_call_cannot_erase_argument_effects():
    with pytest.raises(UserError, match='pure fact term'):
        codegen(SrcFile(None, POSITIVE + 'make=():>int64<v=>v>?0>=>{printl("effect") return 42}\nmain=():>int64=>{positive(make()) return 42}'))


def test_unknown_proof_is_rejected_under_prototype():
    with pytest.raises(UserError, match='refinement'):
        codegen(SrcFile(None, '$prototype\n$proof\npositive=(x:int64):> <x>?0> => {}\nmain=():>int64=>{positive(42) return 42}'))


def test_prototype_cannot_defer_an_erased_argument_obligation():
    with pytest.raises(UserError):
        codegen(SrcFile(None, '$prototype\n' + POSITIVE + 'invoke_proof=(n:int64)=>{positive(n)} main=():>int64=>{invoke_proof(42) return 42}'))


def test_bare_fact_return_is_proof_only():
    with pytest.raises(UserError, match='only for.*proof'):
        codegen(SrcFile(None, 'positive=(x:int64<v=>v>?0>):> <x>?0> => {}'))


def test_ordered_proofs_and_finite_composition(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/checked_proofs.dewy'
    emitted = codegen(SrcFile.from_path(fixture))
    assert 'positive_again' not in emitted and 'ordered' not in emitted
    execute(tmp_path, 'composed-proofs', emitted)


@pytest.mark.parametrize('use', [
    'ordered(3 2 1)', 'ordered(1 c=2 b=3)',
])
def test_dependent_preconditions_check_actual_literals(use):
    source = '$proof\nordered=(a:int64 b:int64<v=>a<=?v> c:int64<v=>b<=?v>):> <a<=?c> => {}\n'
    with pytest.raises(UserError, match='refinement'):
        codegen(SrcFile(None, source + f'main=():>int64=>{{{use} return 42}}'))


def test_proof_call_graph_rejects_mutual_recursion():
    source = '''$proof
alpha=(x:int64):> <x>?0> => {beta(x)}
$proof
beta=(x:int64):> <x>?0> => {alpha(x)}
'''
    with pytest.raises(UserError, match='acyclic|depend on itself'):
        codegen(SrcFile(None, source))


def test_direct_imported_proof(tmp_path):
    (tmp_path / 'proofs.dewy').write_text(POSITIVE)
    main = tmp_path / 'main.dewy'
    main.write_text('import p"proofs.dewy" as proofs\nmain=():>int64=>{proofs.positive(42) return 42}')
    emitted = codegen(SrcFile.from_path(main))
    assert 'positive' not in emitted
    execute(tmp_path, 'imported-proof', emitted)


def test_proof_fact_does_not_survive_argument_assignment():
    source = POSITIVE + '''main=():>int64=>{
        let n:int64=42
        positive(n)
        n=-1
        $assert n>?0
        return 42
    }'''
    with pytest.raises(UserError, match='assertion'):
        codegen(SrcFile(None, source))


@pytest.mark.parametrize('comparison', ['a <? b', 'a >? b', 'a not=? b'])
def test_nonstrict_order_does_not_imply_strict_order(comparison):
    with pytest.raises(UserError, match='assertion'):
        codegen(SrcFile(None, f'f=(a:int64 b:int64<v=>a<=?v>)=>{{$assert {comparison}}}'))


def test_proof_declaration_cannot_be_replaced():
    with pytest.raises(UserError, match='proof declaration|read.only'):
        codegen(SrcFile(None, POSITIVE + 'positive=(x:int64):>void & <x>?0>=>{printl("effect")}'))


def test_proof_callback_argument_is_rejected():
    with pytest.raises(UserError, match='proof'):
        codegen(SrcFile(None, POSITIVE + 'take=(f:((x:int64):>void))=>{}\nmain=():>int64=>{take(positive) return 42}'))


def test_proof_does_not_bypass_precondition_on_mutable_argument():
    with pytest.raises(UserError, match='refinement'):
        codegen(SrcFile(None, POSITIVE + 'main=():>int64=>{let n:int64=42\npositive(n)\nn=-1\npositive(n)\nreturn 42}'))


@pytest.mark.parametrize('condition', ['x+1 >? x', 'x-1 <? x', '(x+2)-1 >? x'])
def test_order_proofs_do_not_assume_word_arithmetic_cannot_wrap(condition):
    with pytest.raises(UserError, match='assertion'):
        codegen(SrcFile(None, f'f=(x:int64)=>{{$assert {condition}}}'))


def test_order_proofs_accept_guarded_affine_terms():
    codegen(SrcFile(None, 'f=(x:int64)=>{if x <? 9223372036854775807 {$assert x+1 >? x}}'))


def test_record_variant_field_after_loop_uses_current_owner(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/nominal_field_after_loop.dewy'
    execute(tmp_path, 'variant-after-loop', codegen(SrcFile.from_path(fixture)))
