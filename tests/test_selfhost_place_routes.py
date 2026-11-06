"""Place identities: alias roots, interning and routes match frozen Jo."""
import re

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/places.jo').read_text())
SERVICES = r'''use 'source_types.dewy'
use 'node_store.dewy'
use 'checker_types.dewy'
use 'checker_state.dewy'
const LF_ALIAS = 8
const T_RECORD = 7
nodes: Node[] = [Node()]
locals: Local[] = [Local()]
ntype = (n: int) -> int: int(nodes[n].type)
tkind = (t: int) -> TK: if t == T_RECORD: .struct_ else: .int_
'''

DRIVER = r'''
use 'places.jo'
n_ = (k: NK, a: int = 0, sym: int = 0, aux: int = 0, name: int = 0, t: int = T_RECORD) -> int:
    nodes.push(Node(kind=k, a=i32(a), sym=i32(sym), aux=i32(aux), name=i32(name), type=i32(t)))
    nodes.len() - 1
local = (l: int) -> int: n_(.ident, 0, l, int(SK.local))
global = (g: int) -> int: n_(.ident, 0, g, int(SK.global))
field = (a: int, name: int) -> int: n_(.field, a, 0, 0, name)
show = (p: PlaceIdentity): print("{p.root == .local} {p.owner} {p.declaration} {p.parent} {p.projection == .root} {p.selector}")
alias = (target: int) -> int:
    locals.push(Local(flags=i32(LF_ALIAS), alias=i32(target), owner=77))
    locals.len() - 1
main = ():
    loop i in [1..6): locals.push(Local(owner=i32(i * 10)))
    # Scalar roots: nothing, an address, a non-identifier, globals, others, locals and aliases.
    loop e in [0, n_(.addr, local(1)), n_(.int_lit), global(3), n_(.ident, 0, 2, int(SK.fns)), local(2)]: show(place_scalar_root(e))
    a = alias(local(3))
    show(place_scalar_root(local(a)))
    aa = alias(local(a))
    show(place_scalar_root(local(aa)))
    show(place_scalar_root(local(alias(global(1)))))
    show(place_scalar_root(local(alias(n_(.int_lit)))))
    empty = alias(0); locals[empty].alias = 0
    show(place_scalar_root(local(empty)))
    chain = local(3)
    loop i in [0..40): chain = local(alias(chain))
    show(place_scalar_root(chain))
    chain = local(4)
    loop i in [0..32): chain = local(alias(chain))
    show(place_scalar_root(chain))
    locked = alias(local(3))
    place_locked[locked] = true
    show(place_scalar_root(local(locked)))
    # Interning and projection.
    root = PlaceIdentity(.local, 1, 2)
    print(place_intern(root)); print(place_intern(root)); print(place_intern(PlaceIdentity(.global, 0, 9)))
    print(place_parents.len())
    show(place_project(PlaceIdentity(.local, 0, 0), 5))
    p = root
    loop i in [0..10):
        p = place_project(p, i + 1)
        show(p)
    # Routes: depth, addresses, fields of records and of others, aliases, bounds.
    show(place_route(0))
    show(place_route(local(1), 33))
    show(place_route(n_(.addr, field(local(1), 5))))
    show(place_route(field(field(local(1), 5), 6)))
    show(place_route(field(n_(.ident, 0, 1, int(SK.local), 0, 3), 5)))
    show(place_route(local(0)))
    show(place_route(local(locals.len() + 3)))
    show(place_route(field(local(a), 8)))
    show(place_route(local(locked)))
    show(place_route(global(1)))
    deep = local(1)
    loop i in [0..40): deep = n_(.addr, deep)
    show(place_route(deep))
    # Paths and appending.
    route = place_project(place_project(root, 21), 22)
    print(place_path(route)); print(place_path(root))
    base = PlaceIdentity(.global, 0, 4)
    show(place_append(base, root)); show(place_append(base, route))
    print(place_path(place_append(base, route)))
    show(place_append(PlaceIdentity(.local, 0, 0), route))
    places_reset()
    print(place_parents.len()); print(place_intern(root))
    print("routes ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_place_routes_twins(compiler, tmp_path, release):  # noqa: F811
    output = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'checker_types', 'checker_state', 'dewy_reader_types', 'effect_types', 'place_routes'), DRIVER,
                            doubles={'services.jo': SERVICES, 'places.jo': "use 'effect_types.dewy'\n" + STATE}, services=('ast', 'check', 'expr', 'types'))
    assert output.endswith(b'routes ok\n')
