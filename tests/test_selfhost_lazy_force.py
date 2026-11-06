"""Forcing waiting bodies, replaying eagerly and flushing warnings match frozen Jo."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
struct Module:
    file: i32
    decls: int[]
nodes: Node[]
modules: Module[]
pc_child = -1
pc_reordered = false
pc_cancel = (): print("cancel")
source_force_body = (d: int):
    print("force {d}")
    # (forcing a body may grow the node arena)
    loop i in [0..64): nodes.push(Node())
warn = (pos: int, msg: str): print("warn {pos} {msg}")
'''

DRIVER = r'''
use 'lazy_bodies.jo'
main = ():
    a = args()
    print(a[1..])
    if a.len() > 1 and a[1] == "--eager-bodies": return
    nodes = [Node(), Node(kind=.fn_), Node(kind=.struct_), Node(kind=.fn_), Node(kind=.fn_)]
    modules = [Module(file=0, decls=[1, 2]), Module(file=1, decls=[3]), Module(file=2, decls=[4])]
    dc_force_all()
    dc_lazy_used = true
    dc_lib_lazy_files = {1: true}
    dc_force_all()
    loop m in [0, 1, 2]: dc_force_module(m)
    dc_lazy_used = false
    dc_warning_pos = [5, 6]; dc_warning_text = ["five", "six"]
    dc_replay()
    print("no replay")
    dc_lazy_used = true
    pc_reordered = true
    dc_flush_warnings()
    assert(not dc_lazy_used and not pc_reordered and dc_warning_pos.len() == 0 and dc_warning_text.len() == 0)
    if a.len() > 1 and a[1] == "child":
        pc_child = 0; pc_reordered = true
        dc_replay()
    if a.len() > 1 and a[1] == "replay":
        pc_reordered = true
        dc_replay()
    print("end")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_lazy_force_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'lazy_force'), DRIVER,
                             doubles={'services.jo': SERVICES, 'lazy_bodies.jo': (ROOT / 'compiler/lazy_bodies.jo').read_text()},
                             services=('frontend', 'check', 'pcheck', 'util', 'ast'),
                             invocations=[((), 0), (('child',), 1), (('replay', 'x'), 0)])
    assert b'force 3' in outputs[0] and b'warn 6 six' in outputs[0] and outputs[0].endswith(b'end\n')
    # (a replay starts over: what was printed is dropped, and the arguments lead with the flag)
    assert outputs[2] == b'["--eager-bodies", "replay", "x"]\n'
