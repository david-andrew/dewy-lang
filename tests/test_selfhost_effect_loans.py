"""The scoped-loan pass (effect_loans) matches its frozen Jo twin."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_ownership_checks import STEMS as CHECK_STEMS

STEMS = CHECK_STEMS + ('dewy_reader_types', 'effect_types', 'effect_lattice', 'effect_loans')

# Intrinsic ordinals: lend 1, address 2, length 3, load 4, store 5, len 6,
# runtime_assert 7, static_assert 8, assert 9; anything else is another one.
DRIVER = r'''
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
fns: FnInst[] = [FnInst()]
owners: {int: bool} = {}
parents: PlaceIdentity[] = [PlaceIdentity()]
contracts: EffectContract[] = [EffectContract()]
lattice = EffectLatticeInput(&contracts, &parents)
lattice_binding = effect_lattice_bind(&lattice)
routes: {int: PlaceIdentity} = {}
summaries: {int: EffectEvent[]} = {}
demanded: {int: bool} = {}
events: str[]
l_error = (n: int, message: str):
    print(events)
    print("error:{n}:{message}")
    exit(23)
l_route = (n: int) -> PlaceIdentity:
    events.push("route:{n}")
    if let p = routes.get(n): return p
    if nodes[n].kind == .ident: return PlaceIdentity(.local, 0, int(nodes[n].sym))
    PlaceIdentity()
l_append = (n: int, p: PlaceIdentity) -> PlaceIdentity:
    events.push("append:{n}:{p.declaration}")
    l_route(n)
l_demand = (f: int) -> bool:
    events.push("demand:{f}")
    demanded.has(f)
l_events = (f: int) -> EffectEvent[]: summaries.get(f) ?? []
host = EffectLoanHost(l_error, l_route, l_append, l_demand, l_events)
input = EffectLoanInput(&nodes, &lists, &locals, &fns, &owners, 1, 2, 3, 4, 5, 6, 7, 8, 9, &host)
binding = effect_loans_bind(&input)
mk = (k: NK, kids: int[] = []) -> int:
    start = lists.len()
    loop c in kids: lists.push(i32(c))
    nodes.push(Node(kind=k, list=i32(start), nlist=i32(kids.len()), pos=nodes.len() * 10))
    nodes.len() - 1
two = (k: NK, a: int, b: int = 0) -> int:
    n = mk(k)
    nodes[n].a = i32(a)
    nodes[n].b = i32(b)
    n
intr = (id: int, kids: int[]) -> int:
    n = mk(.intrinsic, kids)
    nodes[n].aux = i32(id)
    n
local = (flags: int = 0) -> int:
    locals.push(Local(flags=i32(flags)))
    locals.len() - 1
ident = (l: int) -> int:
    n = mk(.ident)
    nodes[n].sym = i32(l)
    nodes[n].aux = 1
    n
decl = (l: int, value: int) -> int:
    n = two(.vardecl, 0, value)
    nodes[n].sym = i32(l)
    n
call = (g: int, kids: int[]) -> int:
    n = mk(.call, kids)
    nodes[n].sym = i32(g)
    n
lend = (owner: int, body: int, writable: bool = true, first: int = 0) -> int:
    n = intr(1, [ident(owner), mk(.int_lit), body])
    if writable: nodes[n].flags = 1
    nodes[n].ival = first
    n
function = (body: int) -> int:
    fns.push(FnInst(body=i32(body)))
    owners[fns.len() - 1] = true
    fns.len() - 1
'''

MAIN = r'''
main = ():
    buf = local()
    x = local()
    y = local()
    z = local()
    w = local()
    # A function walked first: no loan, plain code, an address-free assignment.
    function(mk(.block, [decl(y, mk(.int_lit)), two(.assign, ident(y), mk(.int_lit)), two(.if_, mk(.bool_lit), mk(.block))]))
    g = function(0)
    owners.remove(g)
    demanded[g] = true
    summaries[g] = [EffectEvent(EffectAtom(.write, PlaceIdentity(.formal, 0, 1)), 5), EffectEvent(EffectAtom(.alloc), 6)]
    # Within a writable loan: an address published to a later local, loaded and
    # stored through, the length set, the owner's len, a call whose formal
    # place is another local, an assertion and a loop whose origins settle in
    # two more rounds (w is tainted only after z).
    loop_body = mk(.block, [decl(w, ident(z)), two(.assign, ident(z), intr(2, [ident(buf)]))])
    body = mk(.block, [decl(x, intr(2, [ident(buf)])), intr(5, [mk(.int_lit), ident(x)]), two(.exprstmt, intr(4, [ident(x)])), intr(3, [ident(buf), mk(.int_lit)]), intr(6, [ident(buf)]), call(g, [ident(y)]), intr(7, [mk(.bool_lit)]), two(.while_, mk(.bool_lit), loop_body), mk(.int_lit)])
    f = function(mk(.block, [lend(buf, body, true, x)]))
    loans_finalize()
    print(events)
    print(loan_ids)
    print(loan_generation)
    print(loan_steps)
    print(loan_stack.len())
    print("ok")
'''


def run(compiler, tmp_path, release, driver, status=0):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in STEMS:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in STEMS) + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_effect_loans_twins(compiler, tmp_path, release):  # noqa: F811
    output = run(compiler, tmp_path, release, DRIVER + MAIN)
    assert output.endswith(b'ok\n')
    lines = output.decode().splitlines()
    assert 'demand:' in lines[0] and 'append:' in lines[0]
    # Origins rise three times: x and z in the first round, w in the second.
    assert lines[2] == '3'


ERRORS = [
    ('nested', 'b = local()\n    function(lend(b, lend(b, mk(.int_lit))))', 'nested conflicting loan'),
    ('stable', 'b = local()\n    n = lend(b, mk(.int_lit))\n    routes[kid(n, 0)] = PlaceIdentity(.local, 0, b, 1, .field, 3)\n    function(n)',
     'stable named storage'),
    ('alias', 'b = local(8)\n    function(lend(b, mk(.int_lit)))', 'conflicting alias'),
    ('result', 'b = local()\n    function(lend(b, intr(2, [ident(b)])))', 'as its result'),
    ('inactive', 'b = local()\n    function(intr(2, [ident(b)]))', 'requires an active owner loan'),
    ('readonly', 'b = local()\n    function(lend(b, intr(3, [ident(b), mk(.int_lit)]), false))', 'writable loan'),
    ('outside', 'function(intr(4, [mk(.int_lit)]))', 'requires a scoped loan'),
    ('write', 'b = local()\n    function(lend(b, intr(5, [mk(.int_lit), intr(2, [ident(b)])]), false))', 'readonly loan'),
    ('copy', 'b = local()\n    function(lend(b, two(.exprstmt, ident(b))))', 'owner cannot be copied'),
    ('closure', 'b = local()\n    function(lend(b, mk(.lambda)))', 'closure capture'),
    ('store', 'b = local()\n    d = decl(local(), intr(2, [ident(b)]))\n    nodes[d].flags = 2048\n    function(lend(b, d))',
     'through a store'),
    ('return', 'b = local()\n    function(lend(b, two(.return_, intr(2, [ident(b)]))))', 'through return'),
    ('control', 'b = local()\n    function(lend(b, two(.if_, intr(2, [ident(b)]), mk(.block))))', 'control flow'),
    ('argument', 'b = local()\n    function(lend(b, call(0, [intr(2, [ident(b)])])))', 'through a call'),
    ('contract', 'b = local()\n    function(lend(b, call(0, [])))', 'nonescaping storage contract'),
    ('opaque', 'b = local()\n    g = function(0)\n    demanded[g] = true\n    summaries[g] = [EffectEvent(EffectAtom(.opaque), 1)]\n    function(lend(b, call(g, [])))',
     'may escape or invalidate'),
    ('nonlocal', 'b = local()\n    g = function(0)\n    demanded[g] = true\n    summaries[g] = [EffectEvent(EffectAtom(.read, PlaceIdentity(.global, 0, 4)), 1)]\n    function(lend(b, call(g, [])))',
     'nonlocal loan storage'),
    ('owner', 'b = local()\n    g = function(0)\n    demanded[g] = true\n    summaries[g] = [EffectEvent(EffectAtom(.write, PlaceIdentity(.formal, 0, 1)), 1)]\n    a = mk(.int_lit)\n    routes[a] = PlaceIdentity(.local, 0, b)\n    function(lend(b, call(g, [a])))',
     'active loan owner'),
    ('intrinsic', 'b = local()\n    function(lend(b, intr(20, [])))', 'intrinsic may invalidate'),
    ('aggregate', 'b = local()\n    function(lend(b, mk(.tuple, [intr(2, [ident(b)])])))', 'aggregate storage'),
    ('unsupported', 'b = local()\n    function(lend(b, mk(.fn_)))', 'unsupported address transform'),
    ('replace', 'b = local()\n    t = mk(.int_lit)\n    routes[t] = PlaceIdentity(.global, 0, 2)\n    function(lend(b, two(.assign, t, mk(.int_lit))))',
     'nonlocal replacement'),
]


@pytest.mark.parametrize('name,body,message', ERRORS, ids=[e[0] for e in ERRORS])
def test_effect_loans_errors(compiler, tmp_path, name, body, message):  # noqa: F811
    main = '\nkid = (n: int, i: int) -> int: int(lists[int(nodes[n].list) + i])\nmain = ():\n    ' + body + '\n    loans_finalize()\n    print("unreachable")\n'
    output = run(compiler, tmp_path, False, DRIVER + main, status=23)
    assert message.encode() in output.splitlines()[-1], output[-400:]
