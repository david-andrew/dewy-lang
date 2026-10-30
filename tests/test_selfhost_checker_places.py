"""Address-of, parallel regions, conversions and function references match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xp_seen = 0
xp_contract = false
xp_replacement = 0
xp_nested = 0
xp_snapshot: Node[]
locals: Local[] = [Local()]
xp_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xp_nested != 0:
        inner = xp_nested; xp_nested = 0
        xp_snapshot = nodes
        loop i in [0..256): nodes.push(Node()); locals.push(Local())
        events.push("nested:{xp_check(inner, 0)}")
    xp_seen = n
    if xp_replacement != 0:
        xp_seen = xp_replacement; xp_replacement = 0
    int(nodes[n].type)
xp_contract_host = (n: int, t: int) -> bool:
    events.push("contract:{n}:{t}")
    xp_contract
xp_storage_host = (n: int): events.push("storage:{n}")
xp_error_host = (n: int, code: int):
    print(events)
    print("error:{n}:{code}")
    exit(19)
xp_services = CheckerPlaceHost(xp_check_host, xp_contract_host, xp_storage_host, xp_error_host)
xp_inputs = CheckerPlaceInput(&nodes, &locals, &refine, &xp_seen, &xp_services)
xp_binding = checker_places_bind(&xp_inputs)
operand = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
local = (t: int, flags: int) -> int:
    locals.push(Local(flags = i32(flags)))
    n = operand(t); nodes[n].aux = 1; nodes[n].sym = i32(locals.len() - 1); n
run = (n: int, expected: int = 0):
    t = xp_check(n, expected)
    print("{n}:{t}:{nodes[n].a}:{nodes[n].type}:{xp_seen}:{types[t].kind == .ptr}")
'''

MAIN = r'''
main = ():
    prepare()
    refine = false
    # Parallel regions publish the checked call they wrap.
    replacement = operand(T_FLOAT); xp_replacement = replacement
    region = node(.parallel_region, operand(T_INT))
    run(region, T_INT)
    assert(nodes[region].a == i32(replacement))
    # Addresses: locals live in memory; fields, elements and globals are places too.
    a = local(T_INT, 2)
    run(node(.addr, a))
    assert(locals[int(nodes[a].sym)].flags == 66)
    run(node(.addr, operand(T_STR, .field)))
    run(node(.addr, operand(T_BOOL, .index)))
    g = operand(T_INT); nodes[g].aux = 2; nodes[g].sym = 999
    run(node(.addr, g))
    refine = true
    run(node(.addr, local(T_INT, 0)))
    # Conversions check an unchecked operand again, with a fixed-width hint when marked.
    c = node(.conv, operand(T_INT)); nodes[c].type = i32(T_I32)
    run(c)
    c = node(.conv, operand(T_INT)); nodes[c].type = i32(T_I32); nodes[c].aux2 = 1
    replacement = operand(T_I32); xp_replacement = replacement
    run(c)
    assert(nodes[c].a == i32(replacement))
    checked = operand(T_INT); nodes[checked].flags = i32(128)
    c = node(.conv, checked); nodes[c].type = i32(T_FLOAT)
    run(c)
    c = node(.conv); nodes[c].type = i32(T_FLOAT)
    run(c)
    f = node(.fnref); nodes[f].type = i32(T_BOOL)
    run(f)
    # A nested address grows the node and local arenas before the outer local is marked.
    xp_nested = node(.addr, local(T_INT, 0))
    a = local(T_STR, 1)
    run(node(.addr, a))
    assert(xp_snapshot.len() < nodes.len() and locals[int(nodes[a].sym)].flags == 65)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_places_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_places',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('xp_contract = true; refine = true; xp_check(node(.addr, local(T_INT, 0)), 0)', 1),
    ('xp_check(node(.addr, operand(T_INT, .call)), 0)', 2),
    ('xp_check(node(.addr, local(T_INT, 4)), 0)', 3),
    ('xp_check(node(.hole), 0)', 4),
    ('xp_check(node(.namedarg), 0)', 5),
])
def test_checker_places_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_places',))
    assert output.rstrip().endswith(f':{code}'.encode())
