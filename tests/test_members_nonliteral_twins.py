"""Unsupported literal leaves reach type validation once in either compiler."""
from tests.selfhost_narrow import compare_narrow
from tests.support import ROOT, compiler
from tests.test_selfhost_reflect_ops import SERVICES


DRIVER = r'''
main = ():
    kinds: NK[] = [.str_lit, .int_lit, .binary, .unary, .ident, .tname]
    loop k in kinds:
        n = mk(k, 1)
        nodes[n].type = i32(T_INT)
        nodes[n].aux = 1
        nodes[n].flags = i32(NF_U64)
        nodes[n].op = i32(int(Tok.plus))
        print(members_type(n))
'''


def test_members_nonliteral_twins(compiler, tmp_path):
    state = (ROOT / 'compiler/reflection.jo').read_text()
    state = state[state.index('reflect_active = false'):]
    output = compare_narrow(
        compiler, tmp_path, False,
        ('checker_tokens', 'node_store', 'checker_types', 'checker_state',
         'evaluator_state', 'refinement_types', 'reflect_ops'), DRIVER,
        doubles={'services.jo': SERVICES, 'reflection.jo': state},
        services=('ast', 'check', 'checker_expr', 'comptime', 'expr', 'lex',
                  'member_admit', 'member_replay', 'refine', 'string_domains',
                  'string_domain_ops', 'types', 'util'))
    assert output == b'expr_as_type true\n1\n' * 5 + b'1\n'
