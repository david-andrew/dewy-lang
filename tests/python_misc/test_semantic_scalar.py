from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty


def _main_body(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    declaration = root.items[0]
    assert isinstance(declaration, hir.Declare)
    assert isinstance(declaration.expr, hir.FunctionLiteral)
    assert isinstance(declaration.expr.body, hir.Block)
    return declaration.expr.body


def test_scalar_operator_dispatch() -> None:
    body = _main_body("""
let main = ():>int => {
    let negative:int = -1
    let equal:bool = 1 =? 1
    let ordered:bool = 1 <? 2
    let inverted:bool = 1 not=? 2
    let both:bool = equal and ordered
    return negative
}
""")
    declarations = {
        item.name: item.expr
        for item in body.items
        if isinstance(item, hir.Declare)
    }

    expected = {
        'negative': '__unary_sub__',
        'equal': '__eq__',
        'ordered': '__lt__',
        'inverted': '__ne__',
    }
    for name, dunder in expected.items():
        expr = declarations[name]
        assert isinstance(expr, hir.FunctionCall)
        assert isinstance(expr.func, hir.ExpressedIdentifier)
        assert expr.func.name == dunder

    assert isinstance(declarations['both'], hir.ShortCircuit)
    assert declarations['both'].op == 'and'


def test_assignment_is_void_and_retains_compound_operator() -> None:
    body = _main_body("""
let main = ():>int => {
    let x:int = 40
    x = x + 1
    x += 1
    return x
}
""")
    assignments = [item for item in body.items if isinstance(item, hir.Assign)]

    assert [assignment.op for assignment in assignments] == ['=', '+=']
    assert all(assignment.type == ty.VOID_TYPE for assignment in assignments)
    assert all(assignment.target.name == 'x' for assignment in assignments)


def test_unannotated_integer_let_widens_binding_to_int() -> None:
    body = _main_body("""
let main = ():>int => {
    let x = 10
    x += 1
    return x
}
""")
    declaration = body.items[0]
    assignment = body.items[1]

    assert isinstance(declaration, hir.Declare)
    assert declaration.expr.type == 'int'
    assert isinstance(assignment, hir.Assign)
    assert assignment.target.type == 'int'


def test_assignment_declares_only_an_unbound_identifier() -> None:
    body = _main_body("""
let main = ():>int => {
    x = 10
    x = 11
    return x
}
""")
    declaration = body.items[0]
    assignment = body.items[1]

    assert isinstance(declaration, hir.Declare)
    assert declaration.decltype == 'let'
    assert declaration.name == 'x'
    assert declaration.expr.type == 'int'
    assert isinstance(assignment, hir.Assign)
    assert assignment.target.binding_id == declaration.binding_id


def test_assignment_reuses_a_binding_from_a_parent_scope() -> None:
    body = _main_body("""
let main = ():>int => {
    let x = 10
    {
        x = 11
    }
    return x
}
""")
    declaration = body.items[0]
    nested = body.items[1]

    assert isinstance(declaration, hir.Declare)
    assert isinstance(nested, hir.Block)
    assignment = nested.items[0]
    assert isinstance(assignment, hir.Assign)
    assert assignment.target.binding_id == declaration.binding_id


def test_transmute_is_distinct_from_value_cast() -> None:
    body = _main_body("""
let main = ():>int => {
    return true transmute int
}
""")
    returned = body.items[0]
    assert isinstance(returned, hir.Return)
    assert isinstance(returned.item, hir.Transmute)
    assert returned.item.type == 'int'
    assert isinstance(returned.item.expr, hir.Bool)
    assert not isinstance(returned.item, hir.ValueCast)
