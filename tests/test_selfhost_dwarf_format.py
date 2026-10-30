"""DWARF bytes and state against a frozen twin, including arena-growing callbacks."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

SETUP = r'''
types: TypeInfo[]
type_args: i32[]
structs: StructInfo[]
fields: Field[]
variants: Variant[]
locals: Local[]
globals: Global[]
names: str[]
files: SrcFile[]
global_ids: int[]
ir_positions: int[]
dbg_raw: int[]
dbg_cfi: int[]
line_rows: int[]
T_VOID = 0
T_BOOL = 1
T_INT = 2
T_MATH_INT = 3
T_U8 = 4
T_F32 = 5
T_I32 = 6
global_off: {int: int}
arm = false
grew = false
box_type = -1
host_name = (t: int, dewy: bool) -> str: "type{t}:{dewy}"
host_layout = (t: int):
    if not grew:
        # A layout service may grow every checker arena. The port must refresh
        # element addresses after returning instead of retaining a pointer.
        grew = true
        loop k in [0..256):
            types.push(TypeInfo())
            fields.push(Field())
            variants.push(Variant())
            structs.push(StructInfo())
            names.push("unused")
host_store = (l: int) -> int: int(locals[l].type)
host_field = (f: int) -> int:
    if not fields[f].boxed: return int(fields[f].type)
    if box_type < 0:
        box_type = types.len()
        types.push(TypeInfo(kind=.box, elem=fields[f].type, size=8, align=8))
    box_type
host_line = (id: int) -> int: id * 2
host_module = (m: int) -> bool: m == 0
host = DwarfHost(host_name, host_layout, host_store, host_field, host_line, host_module)
input = DwarfInput(types=&types, type_args=&type_args, structs=&structs, fields=&fields, variants=&variants, locals=&locals, globals=&globals, names=&names, files=&files, global_ids=&global_ids, ir_positions=&ir_positions, dbg_raw=&dbg_raw, dbg_cfi=&dbg_cfi, line_rows=&line_rows, T_VOID=&T_VOID, T_BOOL=&T_BOOL, T_INT=&T_INT, T_MATH_INT=&T_MATH_INT, T_U8=&T_U8, T_F32=&T_F32, T_I32=&T_I32, global_off=&global_off, arm=&arm, host=&host)
binding = dwarf_bind(&input)

reset = ():
    grew = false
    box_type = -1
    # Types 0..6 are the ABI IDs supplied through the input, then compound forms.
    types = [TypeInfo(kind=.void_, size=0, align=1), TypeInfo(kind=.bool_, size=1, align=1), TypeInfo(kind=.int_, bits=64, sign=true, size=8, align=8), TypeInfo(kind=.int_, bits=64, sign=true, size=8, align=8), TypeInfo(kind=.int_, bits=8, size=1, align=1), TypeInfo(kind=.float_, bits=32, size=4, align=4), TypeInfo(kind=.int_, bits=32, sign=true, size=4, align=4), TypeInfo(kind=.str_, size=8, align=8), TypeInfo(kind=.array, elem=2, size=8, align=8), TypeInfo(kind=.ptr, elem=2, size=8, align=8), TypeInfo(kind=.fixed, elem=2, bits=3, size=24, align=8), TypeInfo(kind=.tuple, args=0, nargs=3, size=24, align=8), TypeInfo(kind=.struct_, st=0, size=16, align=8), TypeInfo(kind=.enum_, st=1, size=4, align=4), TypeInfo(kind=.enum_, st=2, size=24, align=8), TypeInfo(kind=.box, elem=12, size=8, align=8), TypeInfo(kind=.fn_, size=16, align=8), TypeInfo(kind=.secret, elem=2, size=8, align=8), TypeInfo(kind=.opt, elem=2, size=16, align=8), TypeInfo(kind=.vec, bits=4, size=16, align=16), TypeInfo(kind=.vec, bits=16, size=64, align=16), TypeInfo(kind=.ptr, elem=0, size=8, align=8), TypeInfo(kind=.null_, size=8, align=8), TypeInfo(kind=.var, ref=2, size=8, align=8)]
    type_args = [i32(2), i32(7), i32(8)]
    names = ["", "left", "next", "value", "A", "B", "x", "y", "global"]
    fields = [Field(name=1, type=2, offset=0), Field(name=2, type=12, offset=8, boxed=true), Field(name=3, type=2, offset=8)]
    structs = [StructInfo(name="Node", fields=0, nfields=2), StructInfo(name="Simple", variants=0, nvariants=2, simple_enum=true), StructInfo(name="Choice", variants=2, nvariants=2, payload_off=8)]
    variants = [Variant(name=4, value=-3), Variant(name=5, value=7), Variant(name=4, fields=2, nfields=1, tag=0), Variant(name=5, fields=3, nfields=0, tag=1)]
    locals = [Local(), Local(name=6, type=12, flags=i32(LF_PARAM)), Local(name=6, type=12, flags=i32(LF_VALUEPARAM | LF_ASSIGNED)), Local(name=7, type=7), Local(name=6, type=8, flags=i32(LF_PARAM | LF_MUTPARAM))]
    globals = [Global(), Global(name=8, type=12, mod=0), Global(name=8, type=2, mod=0, is_const=true), Global(name=8, type=8, mod=1)]
    global_ids = [0, 1, 2, 3]
    global_off = {1: 32, 2: 64, 3: 96}
    files = [SrcFile(path="/root/main.dewy"), SrcFile(path="lib/type.dewy")]
    ir_positions = [0, 1, 8, (1 << 40) | 2, (5 << 40) | 1]
    line_rows = [0, 1, 4, 1, 8, 2, 20, 0, 40, 3, 64, 4]
    dbg_raw = [0, 0, 64, 6, 4, 1, DL_MEM, 6, -24, 4, 20, 2, DL_MEM, 6, -40, 10, 60, 3, DL_CONST, 0, 42, 0, 64, 4, DL_REG, 3, 0, 8, 50]
    dbg_cfi = [0, 64, (if arm: 16 else: 11), 2, 3, -24, 12, -32, 2, 40, 60]
    elf_syms = [("main", 0, 64)]
    dw_data_addr = 0x800000

'''

DRIVER = SETUP + r'''
main = ():
    loop arm0 in [false, true]:
        arm = arm0
        loop dewy in [false, true]:
            reset()
            rows_before = line_rows
            cfi_before = dbg_cfi
            original_types = types
            original_names = names
            path = if dewy: "main.dewy" else: "main.jo"
            sections = dwarf_image(0x400000, 64, path, "test", "/build")
            assert(grew and original_types.len() == 24 and original_names.len() == 9, "layout service growth retained snapshots")
            assert(line_rows == rows_before and dbg_cfi == cfi_before, "read-only line and frame inputs")
            print(sections)
            # Cover every remaining synthetic/type form in the same live context.
            loop t in [0..24): dw_type_die(t)
            loop dw_todo.len() > 0: dw_type_die(dw_todo.pop())
            print(dw_tb)
            print(dw_fix)
            print(dbg_vars(0))
            loop kind in [DL_NONE, DL_REG, DL_MEM, DL_MEMAT, DL_CONST, DL_FCONST, DL_ADDR]:
                loop reg in [0, 4, 8, 32, 65]:
                    out: u8[] = [0xAA]
                    before = out
                    dw_loc_expr(out, kind, reg, -1025)
                    assert(before == [u8(0xAA)], "location expression COW")
                    print(out)
            line_rows = []
            assert(dwarf_image(0, 0, path, "", "").len() == 0, "empty line table")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_dwarf_format_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_state', 'source_types', 'elf_format', 'leb128', 'module_paths', 'json_doc', 'dwarf_format')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
