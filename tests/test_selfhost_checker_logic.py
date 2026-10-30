"""Logical operands, overload rewrites and narrowing scopes match frozen Jo."""
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xg_scopes = CheckerScope()
xg_last = 0
xg_simple = false
xg_overload = 0
xg_mask = false
xg_replacement = 0
xg_nested = 0
xg_nested_at = 0
xg_snapshot: Node[]
xg_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{xg_scopes.names.len()}")
    if xg_nested != 0 and (xg_nested_at == 0 or n == xg_nested_at):
        inner = xg_nested; xg_nested = 0
        xg_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); types.push(TypeInfo())
        assert(xg_check(inner, 0, 0).type == T_BOOL)
    xg_last = n
    if xg_replacement != 0:
        xg_last = xg_replacement; xg_replacement = 0
    if nodes[n].kind == .binary or nodes[n].kind == .unary:
        assert(int(nodes[int(nodes[n].a)].flags) & 128 != 0)
        assert(nodes[n].op == i32(int(Tok.amp)) or nodes[n].op == i32(int(Tok.pipe)) or nodes[n].op == i32(int(Tok.tilde)))
        return T_INT
    if nodes[n].kind == .call: return T_STR
    int(nodes[xg_last].type)
xg_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}:{xg_scopes.names.len()}")
    nodes[n].type = i32(t)
    n
xg_simple_host = (t: int) -> bool: xg_simple
xg_overload_host = (n: int, op: str) -> int:
    events.push("overload:{op}")
    xg_last = -1
    xg_overload
xg_narrow_host = (n: int, holds: bool):
    events.push("narrow:{n}:{holds}")
    xg_scopes.names.push(77)
xg_reset_host = (mark: int):
    events.push("reset:{mark}")
    xg_scopes.names.truncate(mark)
xg_mask_host = (t: int) -> bool: xg_mask
xg_broadcast_host = (n: int):
    assert(int(nodes[int(nodes[n].a)].flags) & 128 != 0)
    nodes[n].kind = .call
xg_services = CheckerLogicHost(xg_check_host, xg_coerce_host, xg_simple_host, xg_overload_host, xg_narrow_host, xg_reset_host, xg_mask_host, xg_broadcast_host)
xg_inputs = CheckerLogicInput(&nodes, &types, &xg_scopes, &xg_last, &T_BOOL, &xg_services)
xg_binding = checker_logic_bind(&xg_inputs)
operand = (t: int) -> int:
    n = node(.ident); nodes[n].type = i32(t); n
logical = (k: NK, a: int, b: int = 0) -> int:
    n = node(k, a); nodes[n].b = i32(b); n
main = ():
    prepare()
    xg_scopes.names.push(9)
    a = operand(T_BOOL); b = operand(T_BOOL)
    loop k in [NK.and_, NK.or_]:
        start = events.len()
        n = logical(k, a, b)
        r = xg_check(n, 0, 0)
        assert(r.type == T_BOOL and not r.bypass)
        assert(events[start] == "check:{a}:0:1")
        assert(events[start + 1] == "coerce:{a}:{T_BOOL}:1")
        assert(events[start + 2] == "narrow:{a}:{k == .and_}")
        assert(events[start + 3] == "check:{b}:{T_BOOL}:2")
        assert(events[start + 4] == "coerce:{b}:{T_BOOL}:2")
        assert(events[start + 5] == "reset:1")
        assert(xg_scopes.names == [9])
    start = events.len()
    assert(xg_check(logical(.not_, a), 0, 0).type == T_BOOL)
    assert(events.len() == start + 2)
    loop k in [NK.and_, NK.or_, NK.not_]:
        ia = operand(T_INT)
        n = logical(k, ia, operand(T_INT))
        snapshot = nodes
        r = xg_check(n, T_INT, T_INT)
        assert(snapshot[n].kind == k and snapshot[ia].flags == 0)
        assert(r.type == T_INT and r.bypass)
        op = if k == .not_: Tok.tilde else if k == .and_: Tok.amp else: Tok.pipe
        assert(nodes[n].op == i32(int(op)))
        assert(nodes[n].kind == (if k == .not_: NK.unary else: NK.binary))
    plain_a = a; plain_b = b
    tuple_type = int(tb_mk_tuple([T_BOOL]))
    a = operand(tuple_type); b = operand(tuple_type)
    xg_overload = T_FLOAT
    loop k in [NK.and_, NK.or_, NK.not_]:
        n = logical(k, a, b)
        start = events.len()
        r = xg_check(n, 0, 0)
        assert(r.type == T_FLOAT and r.bypass and xg_last == n)
        assert(events.len() == start + (if k == .not_: 2 else: 3))
    xg_overload = 0
    assert(not xg_check(logical(.and_, a, b), 0, 0).bypass)
    types.push(TypeInfo(kind = .enum_))
    enum_type = types.len() - 1
    xg_overload = T_FLOAT
    assert(xg_check(logical(.not_, operand(enum_type)), 0, 0).bypass)
    xg_simple = true
    assert(not xg_check(logical(.not_, operand(enum_type)), 0, 0).bypass)
    a = plain_a; b = plain_b
    xg_mask = true
    n = logical(.not_, a)
    r = xg_check(n, 0, 0)
    assert(r.type == T_STR and r.bypass and nodes[n].kind == .call)
    xg_mask = false
    xg_nested = logical(.not_, a)
    replacement = operand(T_BOOL); xg_replacement = replacement
    # The nested operand consumes the replacement; outer checking restores its last ID.
    n = logical(.and_, a, b)
    assert(xg_check(n, 0, 0).type == T_BOOL)
    assert(nodes[n].a == i32(a) and xg_scopes.names == [9])
    xg_nested = logical(.not_, a); xg_nested_at = b
    assert(xg_check(logical(.or_, a, b), 0, 0).type == T_BOOL)
    assert(xg_nested == 0 and xg_scopes.names == [9])
    replacement = operand(T_BOOL); xg_replacement = replacement
    n = logical(.not_, a)
    assert(xg_check(n, 0, 0).type == T_BOOL and nodes[n].a == i32(replacement))
    print(events)
    print("ok")
'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_logic_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER,
                   extra_stems=('checker_logic',)).endswith(b'ok\n')
