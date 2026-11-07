"""Demanded library classification preserves identity, signatures and cache state."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''
use 'main.jo'
use 'effect_library.jo'
use "node_store.dewy"
use "checker_state.dewy"
use "source_types.dewy"
use 'types.jo'
use 'type_ops.dewy'
use 'check.jo'
use 'ast.jo'
use 'util.jo'
make_function = (file: str, name: str, ps: int[], mutable: bool = false) -> int:
    d = nodes.len()
    nodes.push(Node())
    nodes[d].kind = .fn_
    nodes[d].name = i32(intern(name))
    nodes[d].pos = int(files.len()) << 40
    files.push(SrcFile())
    files[files.len() - 1].path = lib_root + file
    f = fns.len()
    fns.push(FnInst())
    fns[f].decl = i32(d)
    fns[f].ret = i32(T_VOID)
    loop i in [0..ps.len()):
        l = locals.len()
        locals.push(Local())
        locals[l].type = i32(ps[i])
        if i == 0 and mutable: locals[l].flags = i32(LF_MUTPARAM)
        fns[f].params.push(l)
    f
main = ():
BINDINGS
    init_types()
    lib_root = "/é/🦊"
    assert(effect_library_class(-1) == .unclassified)
    assert(effect_library_class(999999) == .unclassified)
    assert(effect_library_leaf(T_STR) and effect_library_leaf(T_MATH_INT))
    assert(effect_library_leaf(T_INT) and effect_library_leaf(T_FLOAT) and effect_library_leaf(T_BOOL))
    assert(not effect_library_leaf(mk_array(T_INT)))
    paths = ["/core/rt.jo", "/core/str.jo", "/math_runtime.jo", "/std/graphemes.jo", "/std/dewy.jo", "/std/dewy_sets.jo"]
    names0 = ["__str_eq", "trim", "__mi_parse", "__dewy_string_length", "is_empty", "set"]
    expected: EffectClass[] = [.reads, .allocates, .allocates, .reads, .reads, .allocates]
    loop i in [0..paths.len()):
        f = make_function(paths[i], names0[i], [T_STR])
        assert(effect_library_class(f) == expected[i])
        assert(effect_library_class(f) == expected[i])
        nodes[int(fns[f].decl)].name = i32(intern("unknown"))
        assert(effect_library_class(f) == expected[i])
        effect_library_reset()
        assert(effect_class_text.len() == 0 and effect_class_cache.len() == 0)
        assert(effect_library_class(f) == .unclassified)
    buffer = mk_array(T_U8)
    formatter = make_function("/core/fmt.jo", "__fmt", [buffer, T_STR, T_INT], true)
    assert(effect_library_formatter(formatter))
    assert(effect_library_class(formatter) == .allocates and effect_class_text.has(formatter))
    bad = make_function("/core/fmt.jo", "__fmt", [buffer, T_STR], false)
    assert(not effect_library_formatter(bad) and effect_library_class(bad) == .unclassified)
    spec = make_function("/core/fmt.jo", "__fmt_spec", [buffer, T_STR], true)
    assert(effect_library_class(spec) == .allocates_panics)
    search = make_function("/std/graphemes.jo", "__dewy_find", [T_STR, T_STR])
    search_at = make_function("/std/graphemes.jo", "__dewy_find", [T_STR, T_STR, T_INT])
    assert(effect_library_class(search) == .allocates)
    assert(effect_library_class(search_at) == .allocates_panics)
    outside = make_function("/core/str.jo", "trim", [T_STR])
    files[files.len() - 1].path = "/other/core/str.jo"
    assert(effect_library_class(outside) == .unclassified)
    lib_root = ""
    assert(effect_library_classify(formatter) == .unclassified)
    print("classifiers ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_classifiers(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_classifiers')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    driver = DRIVER.replace('BINDINGS', '    selfhost_test_bind()')
    # Route the complete shared service graph through the differential's module doubles.
    out = compare_leaf(compiler, tmp_path, optimized, driver,
                       extra_stems=('effect_classifiers',), jo_doubles=modules)
    assert out == b'classifiers ok\n'
