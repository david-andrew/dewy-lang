"""Conditional callable values keep every target's access/storage obligations."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from test_scalar_projection import execute

READERS = """read_left=(@xs:array<int64>):>int64=>{if xs.length>?0 return xs[0] return 0}
read_right=(@xs:array<int64>):>int64=>{if xs.length>?0 return xs[0] return 1}
"""
CASES = [
    'a=(x:int64):>int64=>42 b=(x:string):>int64=>0 main=():>int64 & no_effects=>(@a & @b)(1)',
    READERS + """
work=(pick:bool):>int64 & no_effects=>{
    let result:int64=0
    loop i in 0.. and i<?10000 {
        let xs:array<int64>=[42]
        let reader=if pick @read_left else @read_right
        result=reader(@xs)
    }
    return result
}
main=():>int64=>{
    let before:int64=_arena_allocated_bytes
    let result=work(true)+work(false)
    if _arena_allocated_bytes not=?before return 1
    return result//2
}
""", READERS + """
work=(pick:bool):>int64 & no_effects=>{
    let xs:array<int64>=[42]
    return (if pick @read_left else @read_right)(@xs)
}
main=():>int64=>work(false)
"""]
ERRORS = [
    READERS + """replace=(@xs:array<int64>):>int64=>{xs=[1] return 1}
work=(pick:bool):>int64 & no allocates=>{
let xs:array<int64>=[42] let reader=if pick @read_left else @replace return reader(@xs)}""",
    READERS + """work=(pick:bool unknown:(@xs:array<int64>):>int64 & reads<xs>):>int64 & no allocates=>{
let xs:array<int64>=[42] let reader=if pick @read_left else @unknown return reader(@xs)}""",
    READERS + """replace=(@xs:array<int64>):>int64=>{xs=[1] return 1}
work=():>int64 & no allocates=>{
let xs:array<int64>=[42] let reader=@read_left reader=@replace return reader(@xs)}""",
    # Resolving the alternatives must still account for selecting one.
    READERS + """let counter:int64=0
choose=():>bool=>{counter+=1 return true}
work=():>int64 & no_effects=>{
let xs:array<int64>=[42] return (if choose() @read_left else @read_right)(@xs)}""",
]


@pytest.mark.parametrize('source', CASES)
def test_conditional_readers_keep_frame_storage(source, tmp_path):
    execute(tmp_path, 'conditional-places', codegen(SrcFile(None, source)))


@pytest.mark.parametrize('source', ERRORS)
def test_all_conditional_targets_and_selector_effects_are_checked(source):
    with pytest.raises(ReportException, match='effect contract'):
        codegen(SrcFile(None, source))


def test_native_conditional_place_effects(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=ERRORS)


def test_overload_selection_applies_within_each_branch():
    from dewy.reporting import Span
    from dewy.semantic import hir, ty
    from dewy.semantic.analyze.effects import _EffectAnalyzer

    loc = Span(0, 0)
    signature = ty.FunctionType([], [], None, 'void')
    literals = [hir.FunctionLiteral(loc, signature, [], [], None, 'void', hir.Void(loc, 'void'))
                for _ in range(4)]
    overloaded = ty.OverloadType([signature, signature])
    left = hir.OverloadedFunction(loc, overloaded, literals[:2])
    right = hir.OverloadedFunction(loc, overloaded, literals[2:])
    choice = hir.Flow(loc, overloaded, [hir.IfArm(loc, overloaded, hir.Bool(loc, 'bool', True), left)], right)
    call = hir.FunctionCall(loc, 'void', choice, [], {}, selected_method_index=1)
    targets = _EffectAnalyzer(call)._direct_targets(call)
    assert targets is not None
    assert [id(target) for target in targets] == [id(literals[1]), id(literals[3])]


def test_shared_conditional_graph_does_not_enumerate_paths(monkeypatch):
    from dewy.reporting import Span
    from dewy.semantic import hir, ty
    from dewy.semantic.analyze.effects import _EffectAnalyzer

    loc = Span(0, 0)
    signature = ty.FunctionType([], [], None, 'void')
    literal = hir.FunctionLiteral(loc, signature, [], [], None, 'void', hir.Void(loc, 'void'))
    value = literal
    for _ in range(16):
        value = hir.Flow(loc, signature, [hir.IfArm(loc, signature, hir.Bool(loc, 'bool', True), value)], value)
    call = hir.FunctionCall(loc, 'void', value, [], {})
    analysis = _EffectAnalyzer(call)
    visits = 0
    flatten = analysis._flatten_callable

    def counted(*args):
        nonlocal visits
        visits += 1
        return flatten(*args)

    monkeypatch.setattr(analysis, '_flatten_callable', counted)
    assert analysis._direct_targets(call) == [literal]
    assert visits <= 32  # graph-size work, independent of its 65,536 paths


def test_callable_alias_cycle_is_unknown_even_with_a_known_branch():
    from dewy.reporting import Span
    from dewy.semantic import hir, ty
    from dewy.semantic.analyze.effects import _EffectAnalyzer

    loc = Span(0, 0)
    signature = ty.FunctionType([], [], None, 'void')
    literal = hir.FunctionLiteral(loc, signature, [], [], None, 'void', hir.Void(loc, 'void'))
    read = hir.ExpressedIdentifier(loc, signature, 'alias', binding_id=1)
    value = hir.Flow(loc, signature, [hir.IfArm(loc, signature, hir.Bool(loc, 'bool', True), literal)], read)
    declaration = hir.Declare(loc, 'void', 'let', 'alias', signature, value, binding_id=1)
    call = hir.FunctionCall(loc, 'void', read, [], {})
    root = hir.Block(loc, 'void', [declaration, call], True)
    assert _EffectAnalyzer(root)._direct_targets(call) is None
