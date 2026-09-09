"""Literals in type positions denote singleton types."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import NotImplementedYet, TypeCheckError, UserError


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_literal_annotations_are_singleton_types() -> None:
    declared = _declared('let a:5 = 5\nlet s:"one" = "one"\nlet b:0x"6869" = 0x"6869"\n')
    assert declared['a'].annotation == ty.IntegerLiteralType(5)
    assert declared['s'].annotation == ty.StringLiteralType('one')
    assert declared['b'].annotation == ty.BinaryLiteralType(b'hi')


def test_literal_unions_and_type_blocks() -> None:
    declared = _declared('let Mode:type = <1 | 2 | "fast">\nlet f = (m:Mode):>int64 => if m is? "fast" 1 else 0\nlet g = (v:1|2):>int64 => 0\n')
    mode = declared['Mode'].expr.value
    assert isinstance(mode, ty.TypeOr) and ty.StringLiteralType('fast') in mode.items and ty.IntegerLiteralType(1) in mode.items
    # a union of integer singletons at a value boundary is a word with its value set as invariant
    assert declared['g'].expr.type.pos_or_kw[0].type == ty.RefinedType('int64', (ty.Proposition('self', '>=?', 1), ty.Proposition('self', '<=?', 2)))


def test_literal_parameters_specialize_overloads() -> None:
    declared = _declared("""
let DivZero:type = type of error
let safe_div = ((n:int64 d:0):>DivZero => DivZero) & ((n:int64 d:int64 & ~0):>int64 => n // d)
let main = ():>int64 => { let a = safe_div(6 0) let b = safe_div(6 3) return 0 }
""")
    body = declared['main'].expr.body
    calls = [item.expr for item in body.items if isinstance(item, hir.Declare)]
    assert [call.selected_method_index for call in calls] == [0, 1]
    # each call has the selected method's own result type, not a union of all methods'
    assert [str(call.type) for call in calls] == ['DivZero', 'int64']


def test_literal_mismatches_and_unsupported_forms() -> None:
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared('let s:"one" = "two"\n')
    with pytest.raises(TypeCheckError, match='type mismatch'):
        _declared('let n:5 = 6\n')
    with pytest.raises(NotImplementedYet, match='boolean literal type'):
        _declared('let t:true = true\n')


def test_singleton_union_words_reject_other_values() -> None:
    _declared('let s:-1|1 = 1\nlet t:-1|1 = -1\n')
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let s:-1|1 = 0\n')
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let f = (s:-1|1):>-1|1 => 2\n')


def test_a_singleton_branch_beside_a_fixed_width_takes_the_width() -> None:
    """`if previous isnt? none previous.stop else 0` is a `uint64`, not `uint64 | 0`
    (a literal that fits the width); one that does not fit keeps the union."""
    declared = _declared('let T:type = [stop:uint64]\nlet f = (p:T?) => if p isnt? none p.stop else 0\nlet g = (p:T?) => if p isnt? none p.stop else -1\n')
    assert declared['f'].expr.type.ret == 'uint64'
    assert isinstance(declared['g'].expr.type.ret, ty.TypeOr)


def test_a_bare_default_fits_an_inherited_enum_field_by_its_literal() -> None:
    """`type of Report & [severity="error"]` keeps `severity:Severity`: the default's
    literal type is what must fit, not the widened `string`."""
    declared = _declared(
        "let Severity:type = 'error' | 'warning'\n"
        'let Report:type = [severity:Severity title:string = ""]\n'
        'let Error = type of Report & [severity="error"]\n'
        'let e = Error(title="t")\n'
    )
    assert declared['e'].expr.type.fields[0].type == ty.TypeOr([ty.StringLiteralType('error'), ty.StringLiteralType('warning')])
    with pytest.raises((TypeCheckError, UserError), match='weakens field'):
        _declared("let Severity:type = 'error' | 'warning'\nlet Report:type = [severity:Severity]\nlet Odd = type of Report & [severity=\"loud\"]\n")


def test_width_ties_resolve_by_expected_type_then_literal_default() -> None:
    """An overload set on `int64` and `uint64` called on literals alone takes
    `int64`; an expected `uint64` result picks that alternative; a `uint64`
    argument selects it outright."""
    source = (
        'let pick = ((a:int64 b:int64):>int64 => a) & ((a:uint64 b:uint64):>uint64 => b)\n'
        'let x = pick(2 7)\n'
        'let y:uint64 = pick(2 7)\n'
        'let w:uint64 = 3\n'
        'let z = pick(w 9)\n'
    )
    root = check.typecheck_and_resolve(SrcFile(None, source))
    declared = {item.name: item for item in root.items if isinstance(item, hir.Declare)}
    assert declared['x'].expr.type == 'int64'
    assert declared['z'].expr.type == 'uint64'


def test_the_natural_numbers() -> None:
    """`nat64` is `int64 & <(>=? 0)>`, displayed by name (also with more facts);
    `.length` is a `nat64`; a negative literal is refuted; an arbitrary `int64`
    needs a proof; `nat` is the abstract form."""
    from dewy.semantic.hir_display import type_to_dewy
    declared = _declared('let n:nat64 = 3\nlet k = (s:string) => s.length\nlet f = (src:string):>nat64<(<=? src.length)> => 0\nlet a:nat = 1\n')
    assert declared['n'].annotation == ty.RefinedType('int64', (ty.NAT_PROPOSITION,))
    assert type_to_dewy(declared['n'].annotation) == 'nat64'
    assert type_to_dewy(declared['k'].expr.type.ret) == 'addr'   # a length: a natural that fits the address space
    assert type_to_dewy(declared['f'].expr.type.ret) == 'nat64<i => i <=? src.length>'
    assert ty.strip_refinement(declared['a'].annotation) == 'int'
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let n:nat64 = -1\n')
    with pytest.raises((TypeCheckError, UserError), match='cannot prove'):
        _declared('let g = (x:int64):>nat64 => x\n')


def test_the_address_space() -> None:
    """`addr` is a `nat64` that is a position in the target's address space:
    what `.length` is; sums and differences of positions are positions by the
    axiom; a `nat64` or `int64` needs a proof; a product does; a constant at
    or above the cap is refuted."""
    from dewy.semantic.hir_display import type_to_dewy
    declared = _declared('let n:addr = 3\nlet k = (s:string) => s.length\nlet f = (src:string):>addr<(<=? src.length)> => 0\nlet h = (a:addr b:addr):>addr => a + b\n')
    assert declared['n'].annotation == ty.addr_type()
    assert ty.nat_name(declared['n'].annotation) is not None   # an `addr` is a `nat64` with one more fact
    assert type_to_dewy(declared['n'].annotation) == 'addr'
    assert type_to_dewy(declared['k'].expr.type.ret) == 'addr'
    assert type_to_dewy(declared['f'].expr.type.ret) == 'addr<i => i <=? src.length>'
    with pytest.raises((TypeCheckError, UserError), match='refuted'):
        _declared('let n:addr = 0x1_0000_0000_0000\n')
    for source in ('let g = (x:nat64):>addr => x\n', 'let g = (x:int64):>addr => x\n', 'let g = (a:addr):>addr => a * 3\n'):
        with pytest.raises((TypeCheckError, UserError), match='cannot prove'):
            _declared(source)
