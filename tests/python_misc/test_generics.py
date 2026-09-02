"""User generic functions: instantiation per call, hoisted instances, and the rejections."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError

FIRST = "let first = <T>(xs:array<T>):>T|none => if xs.length >? 0 xs[0] else none\n"


def _root(source: str) -> hir.Block:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    assert isinstance(root, hir.Block)
    return root


def _declared(source: str) -> dict[str, hir.Declare]:
    return {item.name: item for item in _root(source).items if isinstance(item, hir.Declare)}


def test_generic_declaration_is_a_placeholder_and_instances_are_hoisted() -> None:
    declared = _declared(FIRST + """
let main = ():>int64 => {
    let xs:array<int64> = [1]
    let ws:array<string> = ["a"]
    let n = first(xs)
    let w = first(ws)
    let again = first(xs)
    return 0
}
""")
    generic = declared['first'].expr
    assert isinstance(generic, hir.GenericFunction) and generic.type.type_params[0].name == 'T'
    assert isinstance(declared['first__int64'].expr, hir.FunctionLiteral)
    assert isinstance(declared['first__string'].expr, hir.FunctionLiteral)
    assert declared['first__int64'].expr.type == ty.FunctionType(
        [ty.PosOrKwArg('xs', ty.ArrayType('int64', None))], [], None, ty.optional('int64'),
    )
    instance_names = [item.name for item in _root(FIRST + "let main = ():>int64 => { let xs:array<int64> = [1] let a = first(xs) let b = first(xs) return 0 }\n").items if item.name.startswith('first__')]
    assert instance_names == ['first__int64']  # one instance per distinct binding


def test_calls_target_the_instance_with_a_concrete_signature() -> None:
    declared = _declared("let pair_sum = <T of int>(a:T b:T):>T => a + b\nlet main = ():>int64 => pair_sum(20 22)\n")
    body = declared['main'].expr.body
    call = body.items[0] if isinstance(body, hir.Block) else body
    while not isinstance(call, hir.FunctionCall):
        call = call.expr
    assert isinstance(call.func, hir.ExpressedIdentifier) and call.func.name == 'pair_sum__int64'
    assert call.type == 'int64'  # literals widen to the word width


def test_literal_bindings_widen_to_ordinary_types() -> None:
    declared = _declared("let swap = <T U>(a:T b:U):>[x:U y:T] => [x=b y=a]\nlet main = ():>int64 => { let s = swap(1 \"one\") return s.y }\n")
    instance = next(item for item in declared.values() if item.name.startswith('swap__'))
    assert instance.expr.type.ret == ty.ObjectType((ty.ObjectField('x', ty.StringType()), ty.ObjectField('y', 'int64')))


def test_generic_bodies_are_checked_at_instantiation() -> None:
    # the body is checked with T bound: `a + a` is fine for int64 …
    _declared("let twice = <T>(a:T):>T => a + a\nlet main = ():>int64 => twice(21)\n")
    # … and rejected for the bool instance, where `+` is not defined
    with pytest.raises((TypeCheckError, UserError)):
        _declared("let twice = <T>(a:T):>T => a + a\nlet main = ():>int64 => { let s = twice(true) return 0 }\n")
    # bounds are enforced at the call
    with pytest.raises((TypeCheckError, UserError), match='no overload takes'):
        _declared("let twice = <T of int>(a:T):>T => a + a\nlet main = ():>int64 => { let s = twice(\"a\") return 0 }\n")


def test_generic_function_rejections() -> None:
    with pytest.raises(UserError, match='needs a declared result type'):
        _declared("let ident = <T>(x:T) => x\n")
    with pytest.raises(UserError, match='must be declared with `let`'):
        _declared("let main = ():>int64 => (<T>(x:T):>T => x)(1)\n")
    with pytest.raises(UserError, match='cannot be used as a value'):
        _declared(FIRST + "let apply = (f:<(xs:array<int64>):>int64|none>):>int64 => 0\nlet main = ():>int64 => apply(@first)\n")
