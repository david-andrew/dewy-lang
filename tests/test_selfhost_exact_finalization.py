"""Final compiler behavior with the exact_finalization leaf and with its frozen twin."""

from tests.selfhost_build_double import compare_golden_cases
from tests.support import compiler  # noqa: F401


def test_exact_finalization_twins(compiler, tmp_path, monkeypatch):
    compare_golden_cases(compiler, tmp_path, monkeypatch, "exact_finalization", (
        "exact_int/wide_unsigned_divisor",
        "exact_int/wide_unsigned_divisor_zero",
        "exact_int/wide_modulo",
        "exact_int/right_shift_observation",
        "exact_loops/cold_accumulator",
        "exact_int/reject_stored",
    ), flags=((), ("--release",)))


def test_exact_finalization_memo_and_operator_widths(compiler, tmp_path, monkeypatch):
    import subprocess

    from tests import selfhost_lsp_double
    from tests.support import ROOT

    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', """use 'main.jo'
use 'ast.jo'
use 'node_store.dewy'
use 'checker_tokens.dewy'
use 'source_types.dewy'
use 'util.jo'
use 'types.jo'
use 'type_ops.dewy'
use 'exact.jo'
use 'exact_finalization.dewy'
main = ():
    init_types()
    files = [SrcFile("case.jo", ".", "x % y"), SrcFile("case.dewy", ".", "x % y", true)]
    unsigned = mk(.int_lit, 1)
    nodes[unsigned].type = i32(T_U64)
    nodes[unsigned].ival = -1
    add_flag(unsigned, NF_U64)
    exact_widths.resize(nodes.len())
    saved = exact_widths
    assert(exact_bits(unsigned) == 65 and saved[unsigned] == 0)
    a = mk(.ident, 1)
    b = mk(.ident, 1)
    n = mk(.binary, mkpos(0, 1))
    nodes[n].a = i32(a)
    nodes[n].b = i32(b)
    nodes[a].type = i32(T_INT)
    nodes[b].type = i32(T_INT)
    nodes[n].type = i32(T_INT)
    exact_marks.resize(nodes.len())
    exact_marks[n] = u8(1)
    exact_widths.resize(nodes.len())
    exact_widths[a] = 7
    exact_widths[b] = 13
    # Isolate operator rules from syntax- and interval-derived upper bounds.
    exact_type_widths.resize(nodes.len())
    exact_type_widths[n] = -1
    nodes[n].op = i32(int(Tok.percent))
    assert(exact_bits(n) == 7)
    nodes[n].pos = mkpos(1, 1)
    exact_widths[n] = 0
    assert(exact_bits(n) == 13)
    nodes[n].op = i32(int(Tok.slash))
    exact_widths[n] = 0
    assert(exact_bits(n) == 8)
    exact_range_meta.resize(nodes.len())
    exact_range_meta[a] = u8(2)
    exact_widths[n] = 0
    assert(exact_bits(n) == 7)
    nodes[n].op = if args()[1] == "shift": i32(int(Tok.shl)) else: i32(int(Tok.starstar))
    exact_widths[n] = 0
    if args()[1] == "bound":
        exact_shifts[n] = 3
        assert(exact_bits(n) == 22)
        print("ok")
    else: print(exact_bits(n))
""")
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('exact_finalization',))
    for mode in ('bound', 'shift', 'power'):
        results = [subprocess.run([binary, mode], capture_output=True, timeout=60) for binary in binaries]
        a, b = [(r.returncode, r.stdout, r.stderr) for r in results]
        assert a == b
        if mode == 'bound':
            assert a == (0, b'ok\n', b'')
        else:
            assert a[0] != 0 and b'cannot prove a finite machine width' in a[2]
