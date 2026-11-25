"""Zoned literals under run-time time policies: open policy reads stand as none, in both twins."""
import pytest
from tests.selfhost_narrow import compare_narrow
from tests.test_selfhost_constant_checks import DRIVER, SERVICES
from tests.support import ROOT, compiler  # noqa: F401

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True])
def test_policy_literal_strict_validation_matches_twins(compiler, tmp_path, release):
    services=SERVICES.replace('intern = (s: str) -> int: 1', 'intern = (s: str) -> int: if s == "time.fold": 2 else if s == "__zone_values": 3 else: 1').replace('''ct_run = (n: int) -> int:
    print(''','''ct_run = (n: int) -> int:
    loop a in kids(n): print("arg {nodes[a].kind == .none_lit} {nodes[a].type} {nodes[a].flags}")
    print(''')
    driver=DRIVER.split('main = ():')[0]+r'''main = ():
    cc_reset()
    files = [PolicySource(path="lib/time/zones.dewy", src="zoned\"2026\"")]
    validator = mk(.fn_, 0)
    decl = mk(.fn_, 0)
    cc_decls[decl] = [CheckConstant([0, 1], validator, "not a zoned time")]
    dir_runtime_policies[2] = true
    literal = (policy_type: int) -> int:
        n = mk(.call, 0)
        nodes[n].type = i32(T_UNION)
        text = mk(.str_lit, 6)
        nodes[text].type = i32(T_STR)
        read = mk(.call, 7)
        nodes[read].type = i32(policy_type)
        set_list(n, [text, read])
        n
    verdict = (t: int, i: int, s: str, items: int[]) -> int:
        ct_values.push(CTValue(type=t, i=i, s=s, items=items))
        ct_values.len() - 1
    # (passing with every open policy as none: narrowed)
    next_value = verdict(T_OPT, 0, "", [])
    n = literal(T_OPT)
    print(cc_call(n, 1, decl))
    print("{nodes[n].kind == .narrow} {cc_passed.has(n)}")
    # (failing: the validator's reason and why the policy is not read)
    message = verdict(T_TEXT, 0, "happens more than once", [])
    next_value = verdict(T_OPT, 1, "", [message])
    print(cc_call(literal(T_OPT), 1, decl))
    # (an open argument that cannot be none: still unsupported)
    print(cc_call(literal(T_TEXT), 1, decl))
    # (a delimited call is not a literal)
    files[0].src = "zoned(\"2026\""
    print(cc_call(literal(T_OPT), 1, decl))
    # (a computed zone alone: the same strict reading, not a refusal)
    dir_runtime_policies = {}
    dir_runtime_policies[3] = true
    files[0].src = "zoned\"2026\""
    next_value = verdict(T_OPT, 0, "", [])
    computed = literal(T_OPT)
    print(cc_call(computed, 1, decl))
    print("computed {nodes[computed].kind == .narrow}")
    print("policy literals ok")
'''
    result=compare_narrow(compiler,tmp_path,release,
        ('source_types','node_store','checker_types','checker_state','checker_tokens','evaluator_state','constant_checks'),driver,
        doubles={'services.jo':services,'check_constant.jo':(ROOT/'compiler/check_constant.jo').read_text()},
        services=('directives','checker_expr','ast','check','expr','types','util','errors','error_ops','comptime','warn_if_ops','constant_folds','unit_rare'))
    assert result.endswith(b'policy literals ok\n')
    for text in (b'computed true', b'arg true 30 128', b'true true', b'not a zoned time: happens more than once (functions here set time policies',
                 b'literal validation through inherited run-time time policies is not yet supported'):
        assert text in result, (text, result)
