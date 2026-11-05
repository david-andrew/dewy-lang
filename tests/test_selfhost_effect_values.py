"""Value effect predicates preserve layout, lifecycle and cached answers."""
import re

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


DRIVER = r'''
use 'main.jo'
use 'effects.jo'
use 'types.jo'
use 'ast.jo'
use "checker_types.dewy"
use "checker_tokens.dewy"
use "node_store.dewy"
record = (ts: int[], boxed: bool = false, hook: bool = false) -> int:
    start = fields.len()
    loop t in ts: fields.push(Field(type=i32(t), boxed=boxed))
    si = structs.len()
    structs.push(StructInfo(fields=i32(start), nfields=i32(ts.len()), resolved=true))
    if hook: structs[si].drop_fn = 1
    t = types.len()
    types.push(TypeInfo(kind=.struct_, st=i32(si), flags=2))
    t
main = ():
    selfhost_test_bind()
    init_types()
    loop t in [T_INT, T_BOOL, T_U64]:
        assert(effect_scalar(t) and effect_plain(t) and effect_share(t) and effect_value(t))
    assert(not effect_scalar(T_MATH_INT) and not effect_scalar(T_FLOAT))
    assert(effect_float(T_FLOAT) and not effect_float(T_INT))
    assert(effect_float_op(.slash) and not effect_word_op(.slash))
    assert(effect_word_op(.shl) and not effect_float_op(.shl))
    assert(effect_word_op(.eq) and effect_float_op(.eq))
    assert(not effect_word_op(.assign) and not effect_float_op(.assign))
    assert(effect_plain(T_VEC2) and not effect_plain(T_STR))
    assert(effect_share(T_STR) and effect_share(T_MATH_INT))
    assert(effect_signature_value(T_MATH_INT) and not effect_signature_value(T_STR))
    arr = mk_array(T_INT)
    assert(not effect_plain(arr) and not effect_share(arr) and effect_value(arr))
    assert(effect_signature_value(arr))
    assert(not effect_value(mk_array(arr)))
    plain = record([T_INT, T_FLOAT])
    share = record([T_INT, T_STR])
    value = record([arr, T_STR])
    boxed = record([T_INT], true)
    hooked = record([T_INT], false, true)
    loop unused in [0..2):
        assert(effect_plain(plain) and effect_plain_type(plain))
        assert(not effect_plain(share) and effect_share(share) and effect_share_type(share, 0))
        assert(not effect_share(value) and effect_value(value) and effect_value_record(value, 0))
        assert(not effect_plain(boxed) and not effect_share(boxed) and not effect_value(boxed))
        assert(not effect_plain(hooked) and not effect_share(hooked) and not effect_value(hooked))
        assert(effect_signature_value(plain) and not effect_signature_value(share))
    assert(effect_plain_cache.has(plain) and effect_share_cache.has(share) and effect_value_cache.has(value))
    assert(effect_plain(mk_fixed(T_INT, 3)))
    assert(not effect_plain(mk_fixed(T_STR, 3)))
    assert(effect_share(mk_opt(T_STR)))
    assert(effect_value(mk_opt(arr)))
    assert(effect_plain(mk_tuple([T_INT, T_FLOAT])))
    assert(effect_share(mk_tuple([T_INT, T_STR])))
    assert(effect_value(mk_tuple([arr, T_STR])))
    assert(not effect_plain_type(plain, 17) and not effect_value_record(value, 9))
    si = structs.len()
    structs.push(StructInfo(simple_enum=true, resolved=true))
    en = types.len()
    types.push(TypeInfo(kind=.enum_, st=i32(si), flags=2))
    assert(effect_simple_enum(en) and effect_plain(en) and not effect_simple_enum(T_INT))
    n = nodes.len()
    nodes.push(Node(kind=.int_lit, type=i32(T_MATH_INT), ival=3))
    assert(effect_count_literal(n))
    nodes[n].ival = -1
    assert(not effect_count_literal(n))
    nodes[n].ival = 3; nodes[n].flags = i32(NF_U64)
    assert(not effect_count_literal(n))
    print("values ok")
'''


@pytest.mark.parametrize('optimized', [False, True], ids=['default', 'release'])
def test_effect_values_execution(compiler, tmp_path, monkeypatch, optimized):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    modules = modules_for(tmp_path / 'unused.dewy', tmp_path / 'unused', 'effect_values')
    bindings = re.findall(r'^    (lower_test_bind_\w+\(\))$', modules['main.jo'], re.M)
    modules['main.jo'] += '\nselfhost_test_bind = ():\n' + ''.join('    ' + b + '\n' for b in bindings)
    out = compare_leaf(compiler, tmp_path, optimized, DRIVER,
                       extra_stems=('effect_values',), jo_doubles=modules)
    assert out == b'values ok\n'
