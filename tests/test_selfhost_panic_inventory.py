"""Panic body inventory, literal obligations and witnesses match frozen code."""
import json
import re
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_panics_effect import PROVED, REJECTED


DRIVER = r'''
use 'main.jo'
use 'effects.jo'
use 'types.jo'
use 'ast.jo'
use 'check.jo'
use 'expr.jo'
use 'util.jo'
use "node_store.dewy"
use "source_types.dewy"
main = ():
    selfhost_test_bind()
    init_types()
    specs = ["", "s", "d", "x", "#x", "+08d", ">8", "0>8x", "^10", ",", "_", ".2", ".2f", "8.2%", "+s", "#d", ",x", ".2d", "1234567890123456789", ".1234567890123456789f", "ä>9", "\xff>9", "bad"]
    loop t in [T_STR, T_INT, T_MATH_INT, T_FLOAT, T_BOOL]:
        loop spec in specs: print(panic_format_spec(spec, t))
    assert(panic_format_spec("#x", T_INT) and panic_format_spec(">8", T_STR))
    assert(panic_format_spec("\xff>9", T_INT))
    assert(not panic_format_spec(".2", T_STR) and not panic_format_spec("x", T_FLOAT))
    text = mk(.str_lit, 0); nodes[text].sval = i32(intern("hello")); nodes[text].type = i32(T_STR)
    assert((panic_literal_texts(text) ?? []) == ["hello"])
    a = mk(.int_lit, 0); nodes[a].ival = 3
    b = mk(.bool_lit, 0); nodes[b].ival = 1
    range = mk(.for_, 0); nodes[range].a = i32(a); nodes[range].c = i32(b)
    assert(panic_literal(a) == a and panic_literal(b) == b and panic_literal_step(range))
    nodes[a].ival = 1; assert(not panic_literal_step(range))
    add_flag(a, NF_U64); assert(panic_literal(a) == 0)
    assert(not panic_device_literal(0) and not panic_atomic_progress(0) and not panic_literal_safe(0))
    unreachable = mk(.intrinsic, 0); nodes[unreachable].aux = i32(int(IN.unreachable))
    assert(not panic_synthesized(unreachable))
    nodes[unreachable].aux2 = i32(RANGE_EXHAUSTION); assert(panic_synthesized(unreachable)); nodes[unreachable].aux2 = 0
    fns.resize(4)
    modules.resize(1)
    files.push(SrcFile())
    d = mk(.fn_, 0); nodes[d].name = i32(intern("__dewy_root"))
    fns[1].decl = i32(d); fns[1].state = 2; fns[1].body = i32(unreachable)
    effect_panics_reset()
    panic_index = fill(0, 4); panic_low = fill(0, 4); panic_answer = fill(0, 4)
    panic_witness = fill(0, 4); panic_via = fill(0, 4); panic_local = fill(0, 4); panic_local_via = fill(0, 4)
    panic_edge_at = fill(0, 4); panic_edge_end = fill(0, 4)
    assert(not panic_host_scan(1) and panic_witness[1] == unreachable)
    assert(effect_shown_name(1) == "root" and starts_with(effect_panic_reason(1), "root: unreachable"))
    assert(not panic_host_opted(unreachable))
    panic_edge(1, 1, a); panic_edge(1, 0, a); panic_edge(1, 99, a)
    assert(panic_edges.len() == 0)
    panic_edge(1, 2, a); assert(panic_edges == [2, a])
    effect_panic_note(2, a, "cannot prove first", true)
    effect_panic_note(2, b, "cannot prove second", false)
    effect_panic_note(2, a, "cannot prove third", true)
    assert(effect_panic_nodes[2] == b and not effect_panic_pending.has(2))
    assert(dir_text(effect_panic_texts[2]) == "second" and dir_text("plain") == "plain")
    effect_panics_reset()
    assert(effect_panic_nodes.len() == 0 and panic_edges.len() == 0 and panic_witness.len() == 0)
    print("panic inventory ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_panic_inventory_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'panic_inventory')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('panic_inventory',), jo_doubles=modules)
    assert out.endswith(b'panic inventory ok\n')


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_panic_inventory_program(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(PROVED)
    driver = ("use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
              f'    print(read_file({json.dumps(str(output))}) ?? "")\n')
    image = compare_leaf(compiler, tmp_path, False, driver,
                         extra_stems=('panic_inventory',),
                         jo_doubles=modules_for(source, output, 'panic_inventory',
                                                flags=('--release',) if optimized else ()))
    assert image == output.read_bytes() + b'\n'
    ran = subprocess.run([output], capture_output=True, timeout=30)
    assert ran.returncode == 0 and ran.stdout == b'[1 5 7] 8 0 [1 5]\n', ran.stderr


@pytest.mark.parametrize('case', ['row', 'format_spec'])
def test_panic_inventory_diagnostics(compiler, tmp_path, monkeypatch, case):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text(REJECTED[case][0])
    modules = modules_for(source, output, 'panic_inventory')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = "use 'main.jo'\nmain = ():\n    lower_test_cli()\n"
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('panic_inventory',), jo_doubles=modules)
    assert b'panic' in out
