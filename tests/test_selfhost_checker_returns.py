"""Return statements: declared, inferred and thrown results match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
fns: FnInst[] = [FnInst()]
ctxs: FnCtx[]
cx = 0
last = 0
sink_at = -1
xt_throws_set = false
xt_thrown_set = false
xt_fits_set = true
xt_union_void = false
xt_grow = false
xt_check = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xt_grow:
        xt_grow = false
        loop i in [0..256): nodes.push(Node()); ctxs.push(FnCtx()); types.push(TypeInfo()); fns.push(FnInst())
    nodes.push(nodes[n])
    last = nodes.len() - 1
    int(nodes[n].type)
xt_coerce = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    n + 1000
xt_place = (n: int): events.push("place:{n}")
xt_sink = (pos: int): events.push("sink:{pos}")
xt_throws = (inst: int) -> bool:
    events.push("throws:{inst}")
    xt_throws_set
xt_thrown = (s: int, t: int) -> bool:
    events.push("thrown:{s}:{t}")
    xt_thrown_set
xt_note = (s: int): events.push("note:{s}")
xt_literal = (n: int) -> int:
    events.push("literal:{n}")
    T_I32
xt_fits = (n: int, a: int, b: int) -> bool:
    events.push("fits:{n}:{a}:{b}")
    xt_fits_set
xt_shaped = (n: int, t: int) -> int:
    events.push("shaped:{n}:{t}")
    n + 2000
xt_void_member = (t: int) -> bool:
    events.push("void-member:{t}")
    xt_union_void
xt_void_value = (s: int, t: int): events.push("void-value:{s}:{t}")
xt_error = (n: int, t: int, code: int):
    print(events)
    print("error:{n}:{t}:{code}")
    exit(19)
xt_services = CheckerReturnHost(xt_check, xt_coerce, xt_place, xt_sink, xt_throws, xt_thrown, xt_note, xt_literal, xt_fits, xt_shaped, xt_void_member, xt_void_value, xt_error)
xt_inputs = CheckerReturnInput(&nodes, &types, &structs, &files, &fns, &ctxs, &cx, &last, &sink_at, &T_VOID, &T_NEVER, &xt_services)
xt_binding = checker_returns_bind(&xt_inputs)
DEWY = 1 << 40
# A function context: its instance kind, declared (or inferred) result.
context = (ret: int, infer: bool = false, kind: int = 0, parent: int = 0, decl: int = 0):
    fns.push(FnInst(kind = i32(kind), decl = i32(decl)))
    ctxs.push(FnCtx(inst = i32(fns.len() - 1), parent = i32(parent), ret = i32(ret), infer_ret = infer))
    cx = ctxs.len() - 1
ret = (value: int = 0, dewy: bool = true) -> int:
    s = node(.return_, value)
    if dewy: nodes[s].pos = DEWY + s
    s
typed = (t: int, k: NK = .ident, flags: int = 0, dewy: bool = true) -> int:
    n = node(k); nodes[n].type = i32(t); nodes[n].flags = i32(flags)
    if dewy: nodes[n].pos = DEWY + n
    n
run = (s: int):
    xt_return(s)
    print("{s}:{nodes[s].a}:{types[int(ctxs[cx].ret)].ref}")
union_type = () -> int:
    structs.push(StructInfo(union_ = true))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
prepare_returns = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_returns()
    # Bare returns: void, an inferred result (void), a union with a void member.
    context(T_VOID); run(ret())
    context(int(tb_mk_var()), true); run(ret())
    xt_throws_set = true
    context(int(tb_mk_var()), true); run(ret())
    xt_throws_set = false
    xt_union_void = true
    context(union_type()); run(ret())
    # Inferred results: unified, literals defaulted, thrown, noted.
    context(int(tb_mk_var()), true); run(ret(typed(T_INT)))
    context(int(tb_mk_var()), true); run(ret(typed(T_INT, .int_lit, 256)))
    xt_thrown_set = true
    context(int(tb_mk_var()), true); run(ret(typed(T_STR)))
    xt_thrown_set = false
    xt_throws_set = true
    context(int(tb_mk_var()), true); run(ret(typed(T_INT)))
    # Declared results: coerced, refined to their base, shaped, inferring throws.
    xt_throws_set = false
    context(T_INT); run(ret(typed(T_I32)))
    types.push(TypeInfo(kind = .refined, elem = i32(T_INT)))
    context(types.len() - 1); run(ret(typed(T_INT)))
    shape = node(.tarray, 0, 1)
    decl = node(.fn_, shape)
    context(T_INT, false, 0, 0, decl); run(ret(typed(T_INT)))
    nodes[shape].ival = 2
    context(T_INT, false, 0, 0, decl); run(ret(typed(T_INT)))
    xt_throws_set = true
    xt_fits_set = false
    xt_thrown_set = true
    context(T_VOID, true); run(ret(typed(T_STR)))
    context(T_INT, true); run(ret(typed(T_STR)))
    xt_fits_set = true
    xt_thrown_set = false
    context(T_INT, true); run(ret(typed(T_INT)))
    xt_throws_set = false
    # Places (`return @x`), sinks, nested top-level closures, Jo never results.
    context(T_INT); run(ret(typed(T_INT, .ident, 1)))
    context(T_INT); run(ret(typed(T_INT, .field, 1, false)))
    context(T_INT); run(ret(typed(T_INT, .call, 1)))
    sink_at = 3
    context(T_INT); run(ret(typed(T_INT, .index, 1)))
    sink_at = -1
    context(T_VOID, false, 4, 0); run(ret())
    context(T_NEVER, true); run(ret())
    context(T_INT); xt_grow = true; run(ret(typed(T_INT)))
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_returns_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_returns',)).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('context(T_VOID, false, 4, -1); run(ret())', 1),
    ('context(T_NEVER); run(ret())', 2),
    ('context(T_VOID); run(ret(typed(T_INT)))', 3),
    ('xt_throws_set = true; context(T_VOID, true); run(ret(typed(T_INT)))', 3),
    ('context(T_INT); run(ret())', 4),
    ('context(union_type()); run(ret())', 4),
])
def test_checker_returns_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_returns()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_returns',))
    assert output.rstrip().endswith(f':{code}'.encode())
