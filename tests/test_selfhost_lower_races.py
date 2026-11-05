"""Parallel callback traversal and race diagnostics match the frozen leaf."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for
from tests.test_selfhost_lower_analysis import DRIVER


def test_lower_races_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    driver = DRIVER + r'''main = ():
    lower_test_cli()
    one = la_node(.int_lit, 0, 0, [], T_INT); nodes[one].ival = 1
    local = la_local(T_INT); f = la_fn(la_node(.assign, local, one))
    locals[int(nodes[local].sym)].owner = i32(f)
    race_scan(int(fns[f].body), f, "parallel", true)
    caller = la_fn(la_call(f)); fns[f].body = i32(la_call(caller))
    race_named(caller, "parallel")
    assert(race_done.contains(f) and race_done.contains(caller))
    # Bodies hidden inside nested functions are not executed by this callback.
    global = la_global("counter", T_INT)
    nested = la_node(.lambda, la_node(.assign, global, one))
    race_scan(nested, f, "parallel", true)
    race_scan(0, f, "parallel", true)
    print("ok")
'''
    out = compare_leaf(compiler, tmp_path, False, driver,
                       extra_stems=('lower_races',),
                       jo_doubles=modules_for(source, output, 'lower_races'))
    assert out == b'ok\n'


@pytest.mark.parametrize('captured', [False, True], ids=['global', 'capture'])
def test_lower_races_diagnostics(compiler, tmp_path, monkeypatch, captured):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output, 'lower_races')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    setup = ('target = la_local(T_INT, LF_CAPTURE)\n    nodes[target].name = i32(intern("counter"))'
             if captured else 'target = la_global("counter", T_INT)')
    driver = DRIVER + '''main = ():
    lower_test_cli()
    ''' + setup + '''
    one = la_node(.int_lit, 0, 0, [], T_INT); nodes[one].ival = 1
    write = la_node(.assign, target, one)
    f = la_fn(write)
    race_scan(write, f, "parallel", true)
    print("unreachable")
'''
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_races',), jo_doubles=modules)
    assert b"must not change" in out and b"'counter'" in out and b'data race' in out
    assert b'unreachable' not in out


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_lower_races_callback_forms(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    driver = DRIVER + r'''use 'source_types.dewy'
main = ():
    lower_test_cli()
    f = la_fn(la_node(.block)); decl = la_node(.ident)
    nodes[decl].name = i32(intern("parallel")); fns[f].decl = i32(decl)
    ty = mk_fn([], T_VOID, 0)
    ref = la_node(.fnref, 0, 0, [], ty); nodes[ref].sym = i32(f)
    race_arg(ref, "named"); assert(race_done.has(f))
    nodes[ref].aux = 2; race_arg(ref, "closure")
    lam = la_node(.lambda, 0, 0, [], ty); nodes[lam].sym = i32(f)
    race_arg(lam, "lambda")
    partial = la_node(.partial, ref); nodes[partial].aux = 1
    race_arg(la_node(.conv, partial), "partial value")
    nodes[partial].aux = 0; nodes[partial].sym = i32(f)
    race_arg(partial, "partial named")
    race_check(f, [ref, la_node(.int_lit, 0, 0, [], T_INT)], -1)
    parallel_direct(0, -1); parallel_direct(f, -1)
    fi = files.len(); files.push(SrcFile(path=lib_dir + "/std/é.dewy"))
    pos = fi << 40
    assert(in_lib(pos) and not in_lib(-1) and not in_lib(files.len() << 40))
    fns[f].parallel_api = true; parallel_direct(f, pos)
    race_check(f, [la_node(.ident, 0, 0, [], ty)], pos)
    # Library named bodies are exempt before their global write is traversed.
    nodes[decl].pos = pos; race_done.clear()
    fns[f].body = i32(la_node(.assign, la_global("library", T_INT), 0))
    race_named(f, "library")
    print("ok")
'''
    out = compare_leaf(compiler, tmp_path, optimized, driver,
                       extra_stems=('lower_races',),
                       jo_doubles=modules_for(source, output, 'lower_races'))
    assert out == b'ok\n'


@pytest.mark.parametrize('case,expected', [
    ('type_as_value(la_node(.int_lit, 0, 0, [], T_INT))', b'this is a type'),
    ('race_arg(la_node(.ident), "parallel")', b'pass a function by name or a lambda'),
    ('parallel_direct(f, -1)', b'only be called directly'),
])
def test_lower_races_entry_errors(compiler, tmp_path, monkeypatch, case, expected):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    source, output = tmp_path / 'input.dewy', tmp_path / 'program'
    source.write_text('main=()=>{}\n')
    modules = modules_for(source, output, 'lower_races')
    modules['util.jo'], count = re.subn(
        r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
        'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
        modules['util.jo'], count=1)
    assert count == 1
    driver = DRIVER + '''main = ():
    lower_test_cli()
    f = la_fn(la_node(.block)); decl = la_node(.ident)
    nodes[decl].name = i32(intern("parallel")); fns[f].decl = i32(decl)
    fns[f].parallel_api = true
    ''' + case + '\n    print("unreachable")\n'
    out = compare_leaf(compiler, tmp_path, False, driver, status=41,
                       extra_stems=('lower_races',), jo_doubles=modules)
    assert expected in out and b'unreachable' not in out
