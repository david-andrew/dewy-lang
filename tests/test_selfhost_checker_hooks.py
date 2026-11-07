"""Checker hooks preserve context, growth and pending-body discovery."""
import re
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_values import DRIVER as BASE, JO as BASE_JO, DOUBLES as BASE_DOUBLES
JO = dict(BASE_JO)
DOUBLES = dict(BASE_DOUBLES)
EXTRA = {'check.jo': {'FK_INIT': 'const FK_INIT = 4',
              'FK_NORMAL': 'const FK_NORMAL = 0',
              'check_scopes': 'check_scopes = CheckerScope()',
              'check_stmt': 'check_stmt = (s: int): events.push("check_stmt"); return',
              'const_view_declare': 'const_view_declare = (l: int, init: int): '
                                    'events.push("const_view_declare"); return',
              'copy_write_warnings': 'copy_write_warnings = (f: int): events.push("copy_write_warnings"); '
                                     'return',
              'ctxs': 'ctxs: FnCtx[]',
              'cx': 'cx = -1',
              'enter_module_context': 'enter_module_context = (m: int) -> bool: '
                                      'events.push("enter_module_context"); false',
              'leave_module_context': 'leave_module_context = (m: int, entered: bool): '
                                      'events.push("leave_module_context"); return',
              'module_ctx': 'module_ctx: int[]',
              'prepare_value_helpers': 'prepare_value_helpers = () -> bool: '
                                       'events.push("prepare_value_helpers"); false',
              'scope_mark': 'scope_mark = () -> int: events.push("scope_mark"); 0',
              'scope_reset': 'scope_reset = (mark: int): events.push("scope_reset"); return',
              'zonk_tree': 'zonk_tree = (root: int): events.push("zonk_tree"); return'},
 'icount.jo': {'IC_CHECK': 'const IC_CHECK = 1',
               'ic_mod': 'ic_mod = (phase: int, m: int) -> int: events.push("ic_mod"); 0',
               'ic_restore': 'ic_restore = (bucket: int): events.push("ic_restore"); return'},
 'types.jo': {'zonk': 'zonk = (t: int) -> int: events.push("zonk"); 0'},
 'definite.jo': {'da_record': 'da_record = (s: int): events.push("da_record"); return'},
 'decimals.jo': {'decimal_assign_begin': 'decimal_assign_begin = (s: int) -> int: '
                                         'events.push("decimal_assign_begin"); 0',
                 'decimal_binding_type': 'decimal_binding_type = (pos: int, t: int) -> int: '
                                         'events.push("decimal_binding_type"); 0',
                 'decimal_check_body': 'decimal_check_body = (f: int): events.push("decimal_check_body"); '
                                       'return',
                 'decimal_local': 'decimal_local = (l: int, pos: int, t: int): events.push("decimal_local"); '
                                  'return',
                 'decimal_wants': 'decimal_wants = (f: int) -> bool: events.push("decimal_wants"); false'},
 'growth.jo': {'growth_assign': 'growth_assign = (s: int): events.push("growth_assign"); return',
               'growth_decl_after': 'growth_decl_after = (s: int, l: int, t: int): '
                                    'events.push("growth_decl_after"); return',
               'growth_decl_before': 'growth_decl_before = (s: int): events.push("growth_decl_before"); '
                                     'return'},
 'ide.jo': {'ide_hint_local': 'ide_hint_local = (s: int, l: int): events.push("ide_hint_local"); return'},
 'string_domains.jo': {'int_domain_declare': 'int_domain_declare = (binding: int, value: int): '
                                             'events.push("int_domain_declare"); return',
                       'string_domain_declare': 'string_domain_declare = (binding: int, value: int): '
                                                'events.push("string_domain_declare"); return'},
 'pcheck.jo': {'pc_try': 'pc_try = (start: int): events.push("pc_try"); return'},
 'sibling_types.jo': {'sibling_annotated': 'sibling_annotated = (d: int, t: int, vt: int) -> bool: '
                                           'events.push("sibling_annotated"); false',
                      'sibling_binding': 'sibling_binding = (s: int, t: int) -> int: '
                                         'events.push("sibling_binding"); 0',
                      'sibling_establish': 'sibling_establish = (l: int): events.push("sibling_establish"); '
                                           'return',
                      'sibling_flow_end': 'sibling_flow_end = (b: int): events.push("sibling_flow_end"); '
                                          'return',
                      'sibling_flow_loops': 'sibling_flow_loops = (s: int): '
                                            'events.push("sibling_flow_loops"); return',
                      'sibling_flow_start': 'sibling_flow_start = (l: int, pos: int): '
                                            'events.push("sibling_flow_start"); return',
                      'sibling_scalar': 'sibling_scalar = (d: int, t: int) -> int: '
                                        'events.push("sibling_scalar"); 0',
                      'sibling_statement': 'sibling_statement = (s: int, b: int): '
                                           'events.push("sibling_statement"); return',
                      'sibling_syntax_type': 'sibling_syntax_type = (v: int) -> int: '
                                             'events.push("sibling_syntax_type"); 0'}}
EXTRA['check.jo']['check_stmt'] = '''check_stmt = (s: int):
    events.push("stmt:{s}:{cx}:{ctxs[cx].floor}")
    hk_snapshot = nodes
    loop j in [0..128): nodes.push(Node())
'''
EXTRA['check.jo']['prepare_value_helpers'] = '''prepare_value_helpers = () -> bool:
    events.push("helpers")
    if hk_helpers:
        hk_helpers = false
        fns.push(FnInst(kind=FK_NORMAL))
        return true
    false
'''
EXTRA['check.jo']['scope_mark'] = 'scope_mark = () -> int: check_scopes.names.len()'
EXTRA['check.jo']['enter_module_context'] = 'enter_module_context = (m: int) -> bool: events.push("enter:{m}"); true'
EXTRA['check.jo']['leave_module_context'] = 'leave_module_context = (m: int, entered: bool): events.push("leave:{m}:{entered}:{cx}")'
EXTRA['decimals.jo']['decimal_wants'] = 'decimal_wants = (f: int) -> bool: f == hk_decimal'
EXTRA['decimals.jo']['decimal_quantity_start'] = 'decimal_quantity_start = (pos: int, b: int, t: int) -> int: t'
EXTRA['decimals.jo']['decimal_check_body'] = 'decimal_check_body = (f: int): events.push("decimal:{f}"); fns[f].state = 2'
EXTRA['decimals.jo']['decimal_binding_type'] = 'decimal_binding_type = (pos: int, t: int) -> int: events.push("binding:{pos}:{t}"); T_INT'
EXTRA['types.jo']['zonk'] = '''zonk = (t: int) -> int:
    hk_locals_snapshot = locals
    loop i in [0..256): locals.push(Local())
    T_INT
'''
for module, text in jo_doubles(EXTRA).items():
    JO[module] = JO.get(module, '') + text
JO['check.jo'] = "use 'checker_state.dewy'\n" + JO['check.jo']
JO['definite_walk.dewy'] = 'from p"definite.jo" import (da_record as record_double)\nda_record=(s:int64):>void=>record_double(s)\n'
JO['definite_walk.jo'] = "use 'definite.jo'\n"
for module in ('decimals.jo',):
    JO[module] = "use 'check.jo'\nuse 'types.jo'\n" + JO[module]

def replace(module, name, definition):
    JO[module] = re.sub(r'(?m)^' + name + r' = [^\n]*(?:\n(?:    [^\n]*|[ \t]*))*', definition.rstrip() + '\n', JO[module])

replace('check.jo', 'check_fn_body', '''check_fn_body = (f: int):
    events.push("body:{f}")
    if hk_error: print("body-error"); exit(46)
    fns[f].state = 2
''')
replace('expr.jo', 'coerce', '''coerce = (n: int, t: int) -> int:
    hk_snapshot = nodes
    loop j in [0..128): nodes.push(Node())
    v = mk(.int_lit, nodes[n].pos); nodes[v].type = i32(t); v
''')
DRIVER = ''.join(f"use '{m}'\n" for m in EXTRA) + BASE + r'''
hk_helpers = true
hk_error = false
hk_decimal = 3
hk_snapshot: Node[]
hk_locals_snapshot: Local[]
hk_prepare = ():
    prepare(); events = []
    ctxs = [FnCtx(floor=9)]; cx = -1; module_ctx = [0]
    check_scopes.names = [1, 2]
    a = va_node(.int_lit, T_INT); b = va_node(.block, 0, [a])
    locals.push(Local(type=i32(T_BOOL)))
    fns = [FnInst(), FnInst(kind=FK_NORMAL), FnInst(kind=FK_INIT, mod=0, body=i32(b), locals=[1]), FnInst(kind=FK_INIT), FnInst(kind=1)]
'''
MAIN = r'''main = ():
    hk_prepare()
    n = va_node(.vardecl); value = va_node(.int_lit, T_INT); nodes[n].b = i32(value)
    loop code in [1..5): block_sibling(n, 7, code)
    loop code in [1..4): assign_begin(n, code)
    decl_annotated(n, T_INT, 3); decl_sibling(n, T_INT, 1); decl_sibling(n, T_INT, 2)
    loop code in [1..11): decl_after(n, 1, T_INT, code)
    assert(decl_literal(n) == T_INT and int(nodes[n].b) != value)
    end = run_pending_functions(0)
    assert(end == 6 and fns.len() == 6 and not hk_helpers)
    assert(fns[1].state == 2 and fns[2].state == 2 and fns[3].state == 2 and fns[4].state == 0 and fns[5].state == 2)
    assert(cx == -1 and ctxs[0].floor == 9 and locals[1].type == i32(T_INT))
    assert(hk_locals_snapshot[1].type == i32(T_BOOL))
    assert(events.contains("decimal:3") and events.contains("leave:0:true:0"))
    print(events)
    loop n in nodes: print("{int(n.kind)}:{n.b}:{n.type}")
    print("ok")
'''
STEMS = ('checker_hooks', 'checker_call_cost', 'checker_call_convert')

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_hooks_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')


def test_checker_hooks_body_error(compiler, tmp_path):
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    hk_prepare(); hk_error = true; run_pending_functions(0)\n    print("unreachable")\n',
                     status=46, extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO)
    assert b'body-error' in output
