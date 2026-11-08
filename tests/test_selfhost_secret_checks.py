"""Secret operations preserve conversions, redaction and callback publication."""
import re

import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER

DRIVER = RESOLVER.split('main = ():')[0] + r'''
last_checked = 0
secret_reveal_name = 2
secret_checks: {int: bool}
secret_compares: {int: bool}
check_result = 0
replacement = 0
coercible = true
refinement_check = false
snapshot: Node[]
check_secret = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    snapshot = nodes
    loop i in [0..128): nodes.push(Node()); types.push(TypeInfo())
    last_checked = n
    if replacement != 0: last_checked = replacement
    nodes[last_checked].type = i32(check_result)
    check_result
wrap_secret = (n: int, cv: CV, t: int):
    events.push("wrap:{n}:{int(cv)}:{t}")
    old = nodes[n]
    a = nodes.len(); nodes.push(old)
    nodes[n] = Node(kind=.conv, a=i32(a), aux=i32(int(cv)), type=i32(t), pos=old.pos)
coerce_secret = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    if refinement_check: wrap_secret(n, CV.refinement, t)
    else: nodes[n].type = i32(t)
    n
can_secret = (n: int, f: int, t: int) -> bool:
    events.push("can:{n}:{f}:{t}")
    coercible
operand = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); nodes[n].name = 1; n
main = ():
    prepare(); events = []
    st = int(tb_mk_secret(T_INT)); sb = int(tb_mk_secret(T_BOOL))
    loop k in [SK.struct_, SK.enum_, SK.alias_, SK.type_]: assert(secret_type_sym(k))
    loop k in [SK.none_, SK.local, SK.global, SK.fns, SK.const_, SK.module, SK.builtin, SK.reflected]: assert(not secret_type_sym(k))
    a = operand(st); secret_reveal(a); assert(nodes[a].type == i32(T_INT))
    before = nodes.len(); secret_reveal(a); assert(nodes.len() == before)
    assert(secret_wrap(a, T_INT) == st)
    member = node(.field, a); nodes[member].name = i32(secret_reveal_name)
    assert(secret_member(member, st) == T_INT and last_checked == member)
    assert(nodes[member].kind == .conv and nodes[member].flags == 128)
    loop op in [Tok.eq, Tok.ne, Tok.lt, Tok.le, Tok.gt, Tok.ge, Tok.plus]:
        a = operand(st); b = operand(st); n = node(.binary, a)
        check_result = T_BOOL
        if op == .plus: check_result = T_INT
        t = secret_binary(n, op, a, b)
        if op == .eq or op == .ne: assert(t == T_BOOL)
        else if op == .plus: assert(t == st)
        else: assert(t == sb and last_checked == n)
        assert(nodes[a].type == i32(T_INT) and nodes[b].type == i32(T_INT))
    a = operand(st); n = node(.unary, a); check_result = T_INT
    assert(secret_unary(n) == st and last_checked == n and snapshot.len() < nodes.len())
    loop t in [T_BOOL, T_VOID, T_NEVER]: assert(secret_result(n, t) == t)
    loop k in [NK.int_lit, NK.float_lit, NK.bool_lit, NK.str_lit]:
        n = operand(T_INT, k); assert(secret_coerce(n, T_INT, st) == n)
        assert(nodes[n].kind == k and nodes[n].type == i32(st))
    n = operand(st); before = nodes.len()
    assert(secret_coerce(n, st, st) == n and nodes.len() == before)
    v = int(tb_mk_var()); n = operand(v)
    assert(secret_coerce(n, v, st) == n and tu_prune(v) == st)
    vs = int(tb_mk_secret(int(tb_mk_var()))); n = operand(vs)
    assert(secret_coerce(n, vs, st) == n)
    refinement_check = true
    n = operand(T_INT); assert(secret_coerce(n, T_INT, st) == n)
    assert(secret_checks.has(int(nodes[n].a)))
    refinement_check = false
    n = operand(sb); assert(secret_coerce(n, sb, st) == n)
    loop t in [int(tb_mk_opt(T_INT)), int(tb_mk_var()), int(tb_mk_param(9))]:
        assert(secret_coerce(n, st, t) == -1)
    assert(secret_hint(operand(st)) == " (`z.reveal` gives its value, where using it is intended)")
    assert(secret_hint(operand(st, .int_lit)) == " (`x.reveal` gives its value, where using it is intended)")
    a = operand(T_INT); replacement = operand(T_INT); check_result = T_INT; n = node(.cast, a)
    assert(secret_cast(n, a, st) == st and last_checked == n and nodes[n].type == i32(st))
    assert(secret_can_coerce(a, T_INT, st) == 1)
    assert(secret_can_coerce(a, st, sb) == 1)
    coercible = false; assert(secret_can_coerce(a, T_INT, st) == 0)
    assert(secret_can_coerce(a, st, int(tb_mk_opt(T_INT))) == -1)
    assert(secret_can_coerce(a, st, T_INT) == 0)
    assert(secret_can_coerce(a, int(tb_mk_var()), T_INT) == 1)
    assert(secret_can_coerce(a, T_INT, int(tb_mk_var())) == 1)
    print(events)
    print("secret checks ok")
'''

JO = jo_doubles({
    'ast.jo': {'NF_CHECKED': 'const NF_CHECKED = 128'},
    'types.jo': {
        'prune': 'prune = (t: int) -> int: int(tu_prune(t))',
        'mk_secret': 'mk_secret = (t: int) -> int: int(tb_mk_secret(t))',
        'tkind': 'tkind = (t: int) -> TK: types[int(tu_prune(t))].kind',
        'type_eq': 'type_eq = (a: int, b: int) -> bool: tu_equal(a, b)',
        'has_var': 'has_var = (t: int) -> bool: tu_has_var(t)',
        'unify': 'unify = (a: int, b: int) -> bool: tu_unify(a, b)',
        'is_union': 'is_union = (t: int) -> bool: false',
        'dt': 'dt = (t: int) -> str: "type-{t}"',
    },
    'expr.jo': {
        'CV': 'enum CV: none_, int_, int2float, float2int, float_, opt, ptr, bits, fn2clos, union_, fixed2arr, arr2fixed, quantity_const, explicit_copy, refinement',
        'ntype': 'ntype = (n: int) -> int: int(nodes[n].type)',
        'wrap_conv': 'wrap_conv = (n: int, cv: CV, t: int): wrap_secret(n, cv, t)',
        'coerce': 'coerce = (n: int, t: int) -> int: coerce_secret(n, t)',
        'can_coerce': 'can_coerce = (n: int, f: int, t: int) -> bool: can_secret(n, f, t)',
    },
    'util.jo': {
        'name_of': 'name_of = (n: int) -> str: names[n]',
        'fatal': 'fatal = (p: int, message: str): print(message); exit(41)',
    },
    'check.jo': {'runtime_fn': 'runtime_fn = (name: str) -> int: 0'},
    'secrets.jo': {},
    'lex.jo': {},
})
JO['secrets.jo'] = "use 'driver.jo'\n"
JO['lex.jo'] = "use 'driver.jo'\n"

# Direct imports resolve each state name at its owning module, as in the compiler.
for module, names in {
    'ast.jo': ('nodes',),
    'types.jo': ('types', 'T_BOOL', 'T_NEVER'),
    'expr.jo': ('last_checked',),
    'secrets.jo': ('secret_reveal_name', 'secret_checks', 'secret_compares'),
}.items():
    for name in names:
        declaration = re.search(r'(?m)^' + name + r'\s*[:=][^\n]*\n', DRIVER)
        assert declaration, name
        JO[module] += declaration[0]
        DRIVER = DRIVER[:declaration.start()] + DRIVER[declaration.end():]
    DRIVER = f"use '{module}'\n" + DRIVER

for module in JO:
    JO[module] = ''.join(f"use '{owner}'\n" for owner in ('ast.jo', 'types.jo', 'expr.jo', 'secrets.jo') if owner != module) + JO[module]
    JO[module] = ''.join(f"use '{stem}.dewy'\n" for stem in (
        'node_store', 'checker_types', 'checker_tokens', 'checker_state',
        'type_constructors', 'type_inference')) + JO[module]

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_secret_checks_twins(compiler, tmp_path, release):
    assert compare_leaf(compiler, tmp_path, release, DRIVER, stub='check_secret',
                        extra_stems=('secret_checks',), jo_doubles=JO).endswith(b'secret checks ok\n')

@pytest.mark.parametrize('case,message', [
    ('member', b"has no member 'z'"),
    ('reveal', b'its value is hidden'),
    ('mismatch', b'type mismatch: expected'),
])
def test_secret_checks_diagnostics(compiler, tmp_path, case, message):
    from tests.selfhost_lower_double import CompilerModules
    driver = DRIVER.split('main = ():')[0] + r'''main = ():
    prepare()
    st = int(tb_mk_secret(T_INT)); a = operand(st)
    if args()[2] == "member":
        n = node(.field, a); nodes[n].name = 1
        secret_member(n, st)
    else:
        coercible = false
        target = T_INT
        if args()[2] == "mismatch": target = T_STR
        secret_coerce(a, st, target)
    assert(false)
'''
    modules = CompilerModules(JO, case, tmp_path / 'unused', ())
    out = compare_leaf(compiler, tmp_path, False, driver, stub='check_secret',
                       status=41, extra_stems=('secret_checks',), jo_doubles=modules)
    assert message in out
