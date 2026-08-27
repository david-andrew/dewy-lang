from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty


def test_and_dispatch_constructs_overloads_only_for_callables() -> None:
    source = """
let f = (x:int):>int => x
let g = (x:string):>string => x
let h = @f & @g
let k = @h & @f
let b = true & false
"""
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)

    declarations = {
        item.name: item.expr
        for item in root.items
        if isinstance(item, hir.Declare)
    }

    h = declarations['h']
    assert isinstance(h, hir.OverloadedFunction)
    assert isinstance(h.type, ty.OverloadType)
    assert len(h.type.methods) == 2
    assert [a.name for a in h.alternates if isinstance(a, hir.ExpressedIdentifier)] == ['f', 'g']

    k = declarations['k']
    assert isinstance(k, hir.OverloadedFunction)
    assert isinstance(k.type, ty.OverloadType)
    assert len(k.type.methods) == 3
    assert [a.name for a in k.alternates if isinstance(a, hir.ExpressedIdentifier)] == ['h', 'f']

    assert isinstance(declarations['b'], hir.ShortCircuit)
