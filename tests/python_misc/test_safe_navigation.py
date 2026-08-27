"""Safe navigation: member access forwards exception alternatives."""
import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.errors import TypeCheckError, UserError

PRELUDE = """
let NotFound:type = type of error
let Address:type = [city:string zip:int64]
let User:type = [name:string address:Address|undefined]
let load = (id:int64):>User|NotFound|undefined => if id >? 0 [name="ada" address=undefined] else NotFound
"""


def _declared(source: str) -> dict[str, hir.Declare]:
    root = check.typecheck_and_resolve(SrcFile(None, source))
    return {item.name: item for item in root.items if isinstance(item, hir.Declare)}


def test_member_access_forwards_the_exception_alternatives() -> None:
    declared = _declared(PRELUDE + "let f = (id:int64):>string|NotFound|undefined => load(id).name\n")
    body = declared['f'].expr.body
    node = body.items[0] if isinstance(body, hir.Block) else body
    while not isinstance(node, hir.ForwardingAccess):
        node = node.expr if hasattr(node, 'expr') else node.item
    assert isinstance(node, hir.ForwardingAccess) and node.field == 'name'
    assert set(node.type.items) == {'string', 'NotFound', 'undefined'}
    assert set(node.exception_type.items) == {'NotFound', 'undefined'}


def test_each_route_segment_applies_the_rule() -> None:
    declared = _declared(PRELUDE + "let f = (id:int64):>string|NotFound|undefined => load(id).address.city\n")
    assert 'f' in declared


def test_every_ordinary_alternative_needs_the_member() -> None:
    # the call/product parse ambiguity resolver reports every reading's reason
    with pytest.raises((TypeCheckError, UserError), match='every ordinary alternative to have `city`'):
        _declared(PRELUDE + "let f = (id:int64):>string|NotFound|undefined => load(id).city\n")


def test_ordinary_unions_do_not_forward() -> None:
    with pytest.raises(TypeCheckError, match='member access requires an object'):
        _declared("let Pair:type = [a:int64]\nlet f = (v:Pair|int64):>int64 => v.a\n")


def test_assignment_through_an_exception_bearing_route_is_rejected() -> None:
    with pytest.raises(UserError, match='assignment through a union route'):
        _declared(PRELUDE + "let f = (id:int64):>void => { let u = load(id)\n    u.name = \"x\" }\n")


def test_statement_level_parse_ambiguity_sinks_into_the_value() -> None:
    _declared("let g = (x:int64):>[n:int64] => [n=x]\nlet f = ():>int64 => g(1).n\nlet h = ():>int64 => { let v = g(2).n return v }\n")


def test_common_members_of_ordinary_unions_read_without_narrowing() -> None:
    declared = _declared("""
let Customer:type = [name:string id:int64]
let Organization:type = [name:string members:int64]
let find = (id:int64):>Customer|Organization => if id >? 0 [name="ada" id=id] else [name="acme" members=3]
let who = (id:int64):>string => find(id).name
""")
    assert 'who' in declared
    with pytest.raises((TypeCheckError, UserError), match='every ordinary alternative to have `id`'):
        _declared("""
let Customer:type = [name:string id:int64]
let Organization:type = [name:string members:int64]
let find = (id:int64):>Customer|Organization => if id >? 0 [name="ada" id=id] else [name="acme" members=3]
let which = (id:int64):>int64 => find(id).id
""")
