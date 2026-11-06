"""The wasm driver's imports, adapters, diagnostics and page publication match frozen Jo."""
import shutil

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = r'''use 'checker_types.dewy'
use 'checker_state.dewy'
use 'node_store.dewy'
use 'ir_types.dewy'
const NF_EXTERN = 512
const LK_INST = 0
const T_FLOAT32 = 1
const WT_I32 = 0x7F
const WT_I64 = 0x7E
const WT_F32 = 0x7D
const WT_F64 = 0x7C
struct LFunc:
    kind: int
    inst: int
    name: str
struct WasmABI:
    imported: bool
    name: str
    params: int[]
    ret: int = -1
    signed: bool[]
nodes: Node[]
types: TypeInfo[]
fns: FnInst[]
lfuncs: LFunc[]
ir: IrFn
wfuncs: IrFn[]
wf_present: bool[]
wm_abi: WasmABI[]
wasm_user_pos: bool[]
ir_positions: int[]
main_code: Ins[]
main_exit_lf = 7
rodata: u8[]
data_size = 16
mt_active_off = 24
wm_error = 0
wm_error_lf = -1
html_missing = ""
lib_dir = "library"
program_js = "// js"
prune = (t: int) -> int: if t >= 100: t - 100 else: t
tkind = (t: int) -> TK: types[prune(t)].kind
has_flag = (n: int, f: int) -> bool: int(nodes[n].flags) & f != 0
name_of = (n: int) -> str: "name{n}"
pos_in_lib = (p: int) -> bool: p % 2 == 0
ice = (msg: str): print("ice: {msg}")
wasm_collect_function = (f: IrFn): print("collect {f.name}")
wasm_image = (inits: int[], main_lf: int, code: Ins[], exit_lf: int, ro: u8[], size: int, active: int) -> u8[]:
    print("image {inits} {main_lf} {exit_lf} {size} {active}")
    [u8(wm_abi.len())]
html_image = (wasm: u8[], title: str, icon: u8[], js: str) -> str: "page {wasm} {title} {icon} {js}"
write_zip = (path: str, names: str[], parts: u8[][]) -> bool:
    print("zip {path} {names} {parts}")
    path != "refused.zip"
'''

DRIVER = r'''
abi = (a: WasmABI): print("{a.imported} {a.name} {a.params} {a.ret} {a.signed}")
main = ():
    types = [TypeInfo(kind=.void_), TypeInfo(kind=.float_, bits=32), TypeInfo(kind=.float_, bits=64), TypeInfo(kind=.int_, bits=64, sign=true), TypeInfo(kind=.int_, bits=32, sign=false), TypeInfo(kind=.bool_)]
    loop t in [1, 2, 3, 4, 5, 101, 103]: print(import_wt(t))
    nodes = [Node(), Node(name=11, flags=i32(NF_EXTERN)), Node(name=12)]
    fns = [FnInst(), FnInst(decl=1, ptypes=[1, 103, 4, 5], ret=2), FnInst(decl=2, ptypes=[3], ret=0), FnInst(decl=2, ret=4)]
    lfuncs = [LFunc(LK_INST, 0, ""), LFunc(LK_INST, 1, "imported"), LFunc(LK_INST, 2, "plain"), LFunc(LK_INST, 3, "exported"), LFunc(1, 1, "helper")]
    loop lf in [0..lfuncs.len()): print(is_import(lf))
    wf_present = [true, false, true, true]
    wfuncs = [IrFn(), IrFn(), IrFn(), IrFn(export_name="out")]
    ir_positions = [0, 1, 2, 3]
    loop err in [0, 1, 2, 3]:
        wm_error = err; wm_error_lf = 2
        print(wasm_module([4, 5], 1, -1))
        loop a in wm_abi: abi(a)
        print(wasm_user_pos)
    wm_error = 0
    ir.name = "current"; wasm_collect()
    print(html_page([u8(1)], "Title", [u8(2)]))
    html_missing = "gone.js"
    print(html_page([], "", []))
    html_missing = ""
    print(write_html("page.html", [u8(1)], "T", []))
    print(write_html("missing/page.html", [u8(1)], "T", []))
    print(write_html("game.zip", [u8(1)], "T", []))
    print(write_html("refused.zip", [u8(1)], "T", []))
    print(wm_read_js("part.js"))
    print(wm_read_js("gone.js"))
    print("wasm output ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_wasm_output_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'

    def fresh():
        shutil.rmtree(run, ignore_errors=True)
        (run / 'library/web').mkdir(parents=True)
        (run / 'library/web/part.js').write_text('// part é\n')
        return run

    output = compare_narrow(compiler, tmp_path, release, ('source_types', 'node_store', 'checker_types', 'checker_state', 'ir_types', 'wasm_output'),
                            DRIVER, doubles={'services.jo': SERVICES}, run_in=fresh,
                            observe=lambda directory: (directory / 'page.html').read_text(),
                            services=('ast', 'types', 'check', 'ir', 'lower', 'util', 'zip', 'wasm_module', 'wasm_emit'))
    assert output.endswith(b'wasm output ok\n')
    for text in (b'ice: native-only', b'ice: native overflow', b'function plain used', b'missing library/web/gone.js', b'// part'):
        assert text in output, text
