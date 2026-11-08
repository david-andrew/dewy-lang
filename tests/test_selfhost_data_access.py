"""Parameter pointer diagnostics agree in the active leaf and bootstrap twin."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.test_selfhost_lower_ptr_reads import DRIVER, JO as POINTER_JO

JO = dict(POINTER_JO)
JO['refine.jo'] = 'representation_type = (t: int) -> int: t\n'
JO['check.jo'] += '\ndewy_at = (pos: int) -> bool: pos > 0\n'
JO['util.jo'] = '''use 'driver.jo'
name_of = (n: int) -> str: names[n]
warn = (pos: int, text: str): print("warning:{text}")
fatal = (pos: int, text: str): print("error:{text}"); exit(43)
'''
JO['ffi_checks.dewy'] = '''from p"driver.jo" import unsafe_mode
ffi_unsafe_at=(pos:int64):>bool=>unsafe_mode
'''
JO['ffi_checks.jo'] = '''use 'driver.jo'
ffi_unsafe_at = (pos: int) -> bool: unsafe_mode
'''
DRIVER = DRIVER + r'''
unsafe_mode = false
make_site = (flags: int = LF_VALUEPARAM) -> int:
    l = lp_local(flags); locals[l].name = i32(intern_text("xs"))
    a = lp_ident(l, int(tb_mk_array(T_INT))); p = lp_data(a)
    nodes[p].pos = 10
    cur_fn = lp_fn(lp_node(.assign, lp_read(p), lp_node(.int_lit)))
    data_access_note(p, a, cur_fn)
    p
'''

MAIN = r'''main = ():
    prepare()
    p = make_site()
    # A pointer only read by the function remains permitted.
    fns[cur_fn].body = i32(lp_read(p)); data_access_finalize()
    # Reset must discard cached body summaries across independent checks.
    data_access_reset(); assert(data_functions.len() == 0 and pr_parent.len() == 0)
    unsafe_mode = true
    p = make_site(); data_access_finalize()
    data_access_reset()
    # Mutable parameters supply their caller's owned storage.
    p = make_site(LF_PARAM | LF_MUTPARAM); assert(data_functions.len() == 0)
    data_access_finalize()
    # An explicit raw pointer parameter already supplies access to pointee storage.
    l = lp_local(LF_PARAM); a = lp_ident(l, T_RAWPTR)
    indexed = lp_node(.index, a, 0, [], int(tb_mk_array(T_INT)))
    assert(data_parameter(indexed) == 0)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True])
def test_data_access_twins(compiler, tmp_path, release):
    output = compare_leaf(compiler, tmp_path, release, DRIVER + MAIN,
                          extra_stems=('data_access', 'lower_ptr_reads'), jo_doubles=JO)
    assert b'warning:data() of plain parameter' in output
    assert output.endswith(b'ok\n')


def test_data_access_rejection_twins(compiler, tmp_path):
    output = compare_leaf(compiler, tmp_path, False,
                          DRIVER + 'main = ():\n    prepare(); make_site(); data_access_finalize()\n',
                          status=43, extra_stems=('data_access', 'lower_ptr_reads'), jo_doubles=JO)
    assert b'error:data() of plain parameter' in output
