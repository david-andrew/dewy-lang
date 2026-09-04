"""Debug line information: statement positions reach the x86_64 backend as `.loc` rows,
`# @loc` markers redirect them to another source, and control-flow labels are assembler-local."""
from udewy import p0, t1
from udewy.backend import get_backend


def assemble(src: str, source_path: str | None = '/work/prog.udewy') -> str:
    return p0.parse(t1.tokenize(src), src, get_backend('x86_64'), source_path=source_path)


PROGRAM = """
let main = ():>int => {
    let a:int = 1
    let b:int = a + 1
    return b
}
"""


def test_statements_report_their_own_lines() -> None:
    asm = assemble(PROGRAM)
    assert '.file 1 "/work/prog.udewy"' in asm
    assert '    .loc 1 3 5' in asm and '    .loc 1 4 5' in asm and '    .loc 1 5 5' in asm


def test_loc_markers_redirect_the_statements_after_them() -> None:
    marked = """
let main = ():>int => {
    # @loc /src/main.dewy:12:9
    let a:int = 1
    let b:int = a + 1
    # @loc /src/main.dewy:13:9
    return b
}
"""
    asm = assemble(marked)
    assert '.file 1 "/src/main.dewy"' in asm
    assert '    .loc 1 12 9' in asm and '    .loc 1 13 9' in asm
    assert asm.count('    .loc 1 12 9') == 1          # `b` repeats the marker's position: reported once
    assert '.file 2 "/work/prog.udewy"' not in asm   # nothing fell back to the udewy source after the marker


def test_without_a_source_path_only_markers_report() -> None:
    asm = assemble(PROGRAM, source_path=None)
    assert '.loc' not in asm and '.file' not in asm


def test_control_flow_labels_are_assembler_local() -> None:
    asm = assemble("""
let main = ():>int => {
    let i:int = 0
    loop i <? 3 { i = i + 1 }
    if i =? 3 { return 1 }
    return 0
}
""")
    assert '.Lloop_start' in asm and '.Lif_end' in asm and '.Lmain_epilogue:' in asm
    assert '\n.loop_start' not in asm and 'main_epilogue:\n' not in asm.replace('.Lmain_epilogue:\n', '')


def test_breakpoint_intrinsic_traps() -> None:
    asm = assemble("""
let main = ():>int => {
    __breakpoint__()
    return 0
}
""")
    assert '    int3' in asm
