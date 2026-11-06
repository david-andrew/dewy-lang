"""Foreign-function attributes and `$export` checks match frozen Jo."""
import re

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = r'''use 'node_store.dewy'
const NF_CABI = 2
const NF_EXTERN = 4
const NF_GENERIC = 8
const NF_MUT = 16
const NF_VOID = 32
target_windows = false
target_macos = false
nodes: Node[] = [Node()]
lists: i32[]
names: str[] = [""]
mk = (k: NK, pos: int) -> int:
    nodes.push(Node(kind=k, pos=pos))
    nodes.len() - 1
kids = (n: int) -> int[]: node_kids(nodes, lists, n)
set_list = (n: int, items: int[]): node_set_list(mut nodes, mut lists, n, items)
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
add_flag = (n: int, f: int): nodes[n].flags = i32(int(nodes[n].flags) | f)
intern = (text: str) -> int:
    names.push(text)
    names.len() - 1
name_of = (n: int) -> str: names[n]
fatal = (pos: int, msg: str) -> never:
    print("fatal {pos}: {msg}")
    exit(41)
bc_str = (text: str, pos: int) -> int:
    n = mk(.str_lit, pos)
    nodes[n].name = i32(intern(text))
    n
'''

DRIVER = r'''
use 'dewy_ffi.jo'
fn_ = (name: str, params: int[] = [], flags: int = 0, typed: bool = true) -> int:
    n = mk(.fn_, 5)
    nodes[n].name = i32(intern(name))
    nodes[n].flags = i32(flags)
    if typed: nodes[n].a = i32(mk(.tname, 6))
    set_list(n, params)
    n
param = (typed: bool = true, flags: int = 0) -> int:
    p = mk(.param, 7)
    nodes[p].flags = i32(flags)
    if typed: nodes[p].a = i32(mk(.tname, 8))
    p
libraries = ():
    loop lib in ["", "c", "m", "SDL2", "my.lib", "dir/x", "é"]: print(dw_ffi_library(lib))
show = (n: int):
    print("{names[int(nodes[n].name)]} {nodes[n].flags} {nodes[n].c}")
    loop at in kids(int(nodes[n].c)): print("{names[int(nodes[at].name)]} {nodes[at].a} {nodes[int(nodes[at].a)].kind == .str_lit} {names[int(nodes[int(nodes[at].a)].name)]}")
main = ():
    a = args()
    case = if a.len() > 1: a[1] else: ""
    if case == "":
        libraries()
        target_windows = true; libraries()
        target_windows = false; target_macos = true; libraries()
        target_macos = false
        print(dw_ffi_attr("name", 3, 4))
        # Attach makes the block once, then adds to it.
        n = fn_("f")
        dw_ffi_attach(n, [int(dw_ffi_attr("a", 1, 2))])
        block = nodes[n].c
        dw_ffi_attach(n, [int(dw_ffi_attr("b", 1, 2)), int(dw_ffi_attr("c", 1, 2))])
        print(block == nodes[n].c)
        print(kids(int(nodes[n].c)).len())
        # C function types, through options only.
        plain = mk(.tname, 1); dw_ffi_c_types(0); dw_ffi_c_types(plain)
        fnt = mk(.tfn, 1); opt = mk(.topt, 1); nodes[opt].a = i32(fnt)
        dw_ffi_c_types(opt)
        print("{nodes[plain].flags} {nodes[fnt].flags} {nodes[opt].flags}")
        # $export: the default symbol and a chosen one.
        dw_export_at(9, "")
        named = fn_("plain", [param()])
        dw_export_attach([named]); show(named)
        print(dw_export_pos)
        dw_export_at(9, "c_name")
        print(dw_export_name)
        voided = fn_("nothing", [], NF_VOID, false)
        dw_export_attach([voided]); show(voided)
    else:
        dw_export_at(9, "")
    if case == "twice": dw_export_at(10, "")
    if case == "none": dw_export_attach([])
    if case == "two": dw_export_attach([fn_("a"), fn_("b")])
    if case == "not a function": dw_export_attach([mk(.vardecl, 1)])
    if case == "extern": dw_export_attach([fn_("x", [], NF_EXTERN)])
    if case == "generic": dw_export_attach([fn_("x", [], NF_GENERIC)])
    if case == "main": dw_export_attach([fn_("main")])
    if case == "mut": dw_export_attach([fn_("x", [param(true, NF_MUT)])])
    if case == "untyped": dw_export_attach([fn_("x", [param(false)])])
    if case == "no result": dw_export_attach([fn_("x", [], 0, false)])
    print("ffi ok")
'''

STATE = re.sub(r"(?m)^(use '[^']*'|#.*)\n", '', (ROOT / 'compiler/dewy_ffi.jo').read_text())
FATAL = ('twice', 'none', 'two', 'not a function', 'extern', 'generic', 'main', 'mut', 'untyped', 'no result')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dewy_ffi_attrs_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'dewy_ffi_attrs'), DRIVER,
                             doubles={'services.jo': SERVICES, 'dewy_ffi.jo': STATE},
                             services=('util', 'ast', 'check', 'expr', 'dewy_nodes', 'dewy_tokens'),
                             invocations=[((), 0)] + [((case,), 41) for case in FATAL])
    assert outputs[0].endswith(b'ffi ok\n') and b'msvcrt.dll' in outputs[0] and b'libSDL2.dylib' in outputs[0] and b'c_name' in outputs[0]
