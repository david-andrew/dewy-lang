"""Calls through function values preserve defaults, argument order and growth."""
import re
import pytest
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import compare
from tests.selfhost_expr_double import jo_doubles
from tests.test_selfhost_checker_call_convert import DRIVER as BASE, JO as BASE_JO, DOUBLES

JO = dict(BASE_JO)
JO["directives.jo"] = "dir_code_any = false\ndir_code_parameter = (n: int, callee: int): pass\n"
def replace(module, name, definition):
    JO[module] = re.sub(r'(?m)^' + name + r' = [^\n]*(?:\n(?:    [^\n]*|[ \t]*))*', definition.rstrip() + '\n', JO[module])
EXTRA = {
    'types.jo': {'fn_label_names': 'fn_label_names = (id: int, count: int) -> int[]: [1, 2]'},
    'poly_closure.jo': {
        'PolyFamily': 'struct PolyFamily:\n    decl: int',
        'poly_families': 'poly_families: PolyFamily[] = [PolyFamily(decl=17)]'},
    'expr.jo': {
        'value_call_error': 'value_call_error = (n: int, ft: int, xs: int[], kind: int): print("call-error:{kind}"); exit(46)',
        'map_args': '''map_args = (names: int[], defs: bool[], xs: int[], out: mut int[], kinds: int[] = [], explain: bool = true) -> str:
    events.push("map:{names}:{defs}:{kinds}")
    if hv_map_error: return "mapping-error"
    out = hv_mapped
    ""
'''},
    'ide.jo': {'never_cascade': 'never_cascade = (pos: int, ft: int): events.push("never")'},
    'util.jo': {'intern': 'intern = (text: str) -> int: intern_text(text)', 'fatal': 'fatal = (pos: int, message: str): print(message); exit(46)'},
}
for module, text in jo_doubles(EXTRA).items(): JO[module] = JO.get(module, '') + text
replace('refine.jo', 'representation_type', '''representation_type = (t: int) -> int:
    events.push("representation:{t}")
    if hv_grow:
        hv_grow = false
        hv_snapshot = nodes
        loop i in [0..1024): nodes.push(Node())
    t
''')
# The resolver's stand-in observes polymorphic dispatch without following it.
JO['checker_call_resolve.dewy'] = 'from p"services.jo" import hv_poly\nresolve_fn_call=(n:int64 name:int64 ds:array<int64> xs:array<int64> expected:int64 closure:int64=0 ufcs:bool=false):>int64=>hv_poly(ds expected closure)\n'
JO['checker_call_resolve.jo'] = "use 'services.jo'\nresolve_fn_call = (n: int, name: int, ds: int[], xs: int[], expected: int, closure: int = 0, ufcs: bool = false) -> int: hv_poly(ds, expected, closure)\n"
JO['services.jo'] += 'hv_poly = (ds: int[], expected: int, closure: int) -> int: events.push("poly:{ds}:{expected}:{closure}"); expected\n'
DRIVER = BASE + r'''
hv_map_error = false
hv_mapped: int[]
hv_grow = false
hv_snapshot: Node[]
hv_fn = (kind: TK = .fn_, count: int = 2, keep: int = 0) -> int:
    t = cv_type(kind, T_BOOL, count)
    types[t].bits = i32(keep); types[t].mutmask = 2
    t
hv_call = (t: int, xs: int[], partial: bool = false) -> int:
    c = cr_arg(.ident, t); n = cr_arg(.call)
    if partial: nodes[n].aux2 = i32(AUX2_PARTIAL)
    result = value_call(n, c, xs, T_FLOAT)
    print("call:{result}:{nodes[n].a}:{nodes[n].sym}:{nodes[n].aux}:{nodes[n].aux2}:{nodes[n].type}")
    if not partial and types[t].kind != .polyfn: assert(nodes[n].type == i32(T_BOOL))
    n
'''
MAIN = r'''main = ():
    prepare(); events = []
    a = cr_arg(); b = cr_arg()
    t = hv_fn()
    hv_grow = true
    n = hv_call(t, [a, b]); assert(not hv_grow and hv_snapshot[n].type == 0)
    hv_call(hv_fn(.cfn), [a, b])
    # Named mapping and evaluation order survive the rewrite.
    types[t].st = 1
    named = cr_arg(.namedarg); nodes[named].a = i32(a)
    hv_mapped = [b, a]
    hv_call(t, [named, b])
    hv_call(t, [a, b], true)
    hole = cr_arg(.hole); hv_call(t, [hole, b], true)
    # Kept defaults fill omitted positions in parameter order.
    d = cr_decl([T_INT, T_INT], defaults=[0, b])
    f = fns.len(); fns.push(FnInst(decl=i32(d), targs=[T_STR]))
    t = hv_fn(keep=f); hv_mapped = [a, 0]
    hv_call(t, [a])
    hv_mapped = [a, b]; hv_call(t, [named, b], true)
    hv_call(hv_fn(.polyfn), [a])
    print(events)
    print("ok")
'''
STEMS = ('checker_call_cost', 'checker_call_convert', 'checker_call_values')
@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_call_values_twins(compiler, tmp_path, release):
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO).endswith(b'ok\n')

@pytest.mark.parametrize('case,message', [
    ('hv_call(T_INT, [])', 'call-error:0'),
    ('hv_call(hv_fn(), [])', 'call-error:1'),
    ('a = cr_arg(.namedarg); hv_call(hv_fn(.cfn, 1), [a])', 'call-error:2'),
    ('a = cr_arg(.hole); hv_call(hv_fn(.cfn, 1), [a])', 'call-error:3'),
    ('a = cr_arg(.namedarg); t = hv_fn(count=1); types[t].st = 1; hv_map_error = true; hv_call(t, [a])', 'mapping-error'),
])
def test_checker_call_values_errors(compiler, tmp_path, case, message):
    output = compare(compiler, tmp_path, False, DRIVER + 'main = ():\n    prepare()\n    ' + case + '\n',
                     status=46, extra_stems=STEMS, doubles=DOUBLES, jo_doubles=JO)
    assert message.encode() in output
