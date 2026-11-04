"""Isolate the call dispatcher from its carved services in expression tests."""
import re

# Signatures at the leaf boundary; bodies stay in the expression driver's Jo doubles.
SIGNATURES = {
    'call_head': {'jo': 'call_head = (n: int, expected: int) -> int:', 'dewy': 'call_head=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_typeapply': {'jo': 'call_typeapply = (n: int, expected: int) -> int:', 'dewy': 'call_typeapply=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_ident_special': {'jo': 'call_ident_special = (n: int, expected: int) -> int:', 'dewy': 'call_ident_special=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_dotname': {'jo': 'call_dotname = (n: int, expected: int) -> int:', 'dewy': 'call_dotname=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_member_prepare': {'jo': 'call_member_prepare = (n: int, callee: int, recv: int, receiver_type: mut int, args: int[], expected: int) -> int:', 'dewy': 'call_member_prepare=(n:CDWord callee:CDWord recv:CDWord @receiver_type:CDWord args:array<int64> expected:CDWord):>CDWord=>', 'args': 'n callee recv @receiver_type args expected', 'joargs': 'n, callee, recv, receiver_type, args, expected'},
    'call_member_type': {'jo': 'call_member_type = (n: int, callee: int, rt: int, fname: int, args: int[], expected: int) -> int:', 'dewy': 'call_member_type=(n:CDWord callee:CDWord rt:CDWord fname:CDWord args:array<int64> expected:CDWord):>CDWord=>', 'args': 'n callee rt fname args expected', 'joargs': 'n, callee, rt, fname, args, expected'},
    'call_member_callable': {'jo': 'call_member_callable = (n: int, callee: int, recv: int, rt: int, fname: int, args: int[], expected: int) -> int:', 'dewy': 'call_member_callable=(n:CDWord callee:CDWord recv:CDWord rt:CDWord fname:CDWord args:array<int64> expected:CDWord):>CDWord=>', 'args': 'n callee recv rt fname args expected', 'joargs': 'n, callee, recv, rt, fname, args, expected'},
    'call_member_tail': {'jo': 'call_member_tail = (n: int, callee: int, recv: int, rt: int, member_name: mut int, args: mut int[], expected: int) -> int:', 'dewy': 'call_member_tail=(n:CDWord callee:CDWord recv:CDWord rt:CDWord @member_name:CDWord @args:array<int64> expected:CDWord):>CDWord=>', 'args': 'n callee recv rt @member_name @args expected', 'joargs': 'n, callee, recv, rt, member_name, args, expected'},
    'call_index': {'jo': 'call_index = (n: int, expected: int) -> int:', 'dewy': 'call_index=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_value': {'jo': 'call_value = (n: int, expected: int) -> int:', 'dewy': 'call_value=(n:CDWord expected:CDWord):>CDWord=>', 'args': 'n expected', 'joargs': 'n, expected'},
    'call_name_early': {'jo': 'call_name_early = (n: int, name: int, mod_scope: int, args: int[], expected: int, ufcs: bool) -> int:', 'dewy': 'call_name_early=(n:CDWord name:CDWord mod_scope:CDWord args:array<int64> expected:CDWord ufcs:bool):>CDWord=>', 'args': 'n name mod_scope args expected ufcs', 'joargs': 'n, name, mod_scope, args, expected, ufcs'},
    'call_name_intrinsic': {'jo': 'call_name_intrinsic = (n: int, ii: int) -> int:', 'dewy': 'call_name_intrinsic=(n:CDWord ii:CDWord):>CDWord=>', 'args': 'n ii', 'joargs': 'n, ii'},
    'call_name_array': {'jo': 'call_name_array = (n: int, name: int, mod_scope: int, args: int[], expected: int, ufcs: bool, ii: int) -> int:', 'dewy': 'call_name_array=(n:CDWord name:CDWord mod_scope:CDWord args:array<int64> expected:CDWord ufcs:bool ii:CDWord):>CDWord=>', 'args': 'n name mod_scope args expected ufcs ii', 'joargs': 'n, name, mod_scope, args, expected, ufcs, ii'},
    'call_name_sym': {'jo': 'call_name_sym = (n: int, name: int, mod_scope: int, s: int, args: int[], expected: int, hidden_assert: bool, decls: mut int[]) -> int:', 'dewy': 'call_name_sym=(n:CDWord name:CDWord mod_scope:CDWord s:CDWord args:array<int64> expected:CDWord hidden_assert:bool @decls:array<int64>):>CDWord=>', 'args': 'n name mod_scope s args expected hidden_assert @decls', 'joargs': 'n, name, mod_scope, s, args, expected, hidden_assert, decls'},
    'call_name_collect': {'jo': 'call_name_collect = (n: int, name: int, mod_scope: int, args: int[], expected: int, ufcs: bool, decls: mut int[]) -> int:', 'dewy': 'call_name_collect=(n:CDWord name:CDWord mod_scope:CDWord args:array<int64> expected:CDWord ufcs:bool @decls:array<int64>):>CDWord=>', 'args': 'n name mod_scope args expected ufcs @decls', 'joargs': 'n, name, mod_scope, args, expected, ufcs, decls'},
}


def isolate_call_services(jo):
    dewy = 'from p"expr.jo" import (' + ' '.join(name + '_double' for name in SIGNATURES) + ')\n'
    twin = "use 'expr.jo'\n"
    for name, sig in SIGNATURES.items():
        jo['expr.jo'], count = re.subn(r'(?m)^' + name + r' = ', name + '_double = ', jo['expr.jo'])
        assert count == 1, name
        header = sig['dewy'].replace('CDWord', 'int64')
        dewy += header + name + '_double(' + sig['args'] + ')\n'
        twin += sig['jo'] + ' ' + name + '_double(' + sig['joargs'] + ')\n'
    jo['checker_call_services.dewy'] = dewy
    jo['checker_call_services.jo'] = twin
