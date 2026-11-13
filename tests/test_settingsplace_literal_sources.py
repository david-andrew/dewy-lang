"""Synthesized literal arguments never scan another file or out-of-range bytes."""
import pytest
from tests.selfhost_narrow import compare_narrow
from tests.test_selfhost_constant_checks import DRIVER, SERVICES
from tests.support import ROOT, compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_literal_policy_source_ranges_match_twins(compiler, tmp_path, release):
    services=SERVICES.replace('pos_file = (p: int) -> int: 0', 'pos_file = (p: int) -> int: p >> 40').replace('pos_off = (p: int) -> int: p', 'pos_off = (p: int) -> int: p & ((1 << 40) - 1)')
    driver=DRIVER.split('main = ():')[0]+r'''main = ():
    cc_reset()
    files = [PolicySource(path="lib/time/zones.dewy", src="x"), PolicySource()]
    validator = mk(.fn_, 0)
    decl = mk(.fn_, 0)
    cc_decls[decl] = [CheckConstant([0], validator, "bad")]
    dir_runtime_policies[1] = true
    loop offset in [500, (1 << 40) | 100]:
        n = mk(.call, 15)
        arg = mk(.str_lit, offset)
        set_list(n, [arg])
        assert(cc_call(n, 1, decl) == 0)
        files[0].src = "x" * 400
    print("ranges ok")
'''
    result=compare_narrow(compiler,tmp_path,release,
        ('source_types','node_store','checker_types','checker_state','checker_tokens','evaluator_state','constant_checks'),driver,
        doubles={'services.jo':services,'check_constant.jo':(ROOT/'compiler/check_constant.jo').read_text()},
        services=('directives','checker_expr','ast','check','expr','types','util','errors','error_ops','comptime','warn_if_ops','constant_folds','unit_rare'))
    assert result==b'ranges ok\n'
