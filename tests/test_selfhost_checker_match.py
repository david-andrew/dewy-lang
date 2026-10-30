"""`match`: patterns, bindings, narrowing, results and exhaustiveness match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
locals: Local[] = [Local()]
xh_scope = CheckerScope()
xh_log: int[]
xh_path_count = 0
xh_sink_at = 0
xh_domain: int[]
xh_high: int[]
xh_known = false
xh_key = ""
xh_within = false
xh_target = 0
xh_string_domain = false
xh_int_domain = false
xh_none_id = 61
xh_grow = false
xh_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}")
    if xh_grow:
        xh_grow = false
        loop i in [0..256): nodes.push(Node()); lists.push(0); types.push(TypeInfo()); locals.push(Local()); structs.push(StructInfo())
    # (a bare variant takes its index in the expected enum, as checking gives it)
    if nodes[n].kind == .dotname and expected != 0 and types[expected].kind == .enum_ and nodes[n].name != 0:
        si = int(types[expected].st)
        loop v in [0..int(structs[si].nvariants)):
            if variants[int(structs[si].variants) + v].name == nodes[n].name: nodes[n].aux = i32(v)
    int(nodes[n].type)
xh_finalize_host = (n: int) -> int:
    events.push("finalize:{n}")
    int(nodes[n].type)
xh_coerce_host = (n: int, t: int) -> int:
    events.push("coerce:{n}:{t}")
    nodes[n].type = i32(t)
    n
xh_check_to_host = (n: int, t: int) -> int:
    events.push("check-to:{n}:{t}")
    t
xh_binding_host = (name: int, t: int, pos: int) -> int:
    locals.push(Local(name = i32(name), type = i32(t)))
    events.push("local:{locals.len() - 1}:{name}:{t}")
    locals.len() - 1
xh_fields_host = (si: int):
    events.push("fields:{si}")
    structs[si].resolved = true
xh_intervals_host = (t: int, domain: mut int[], high: mut int[]) -> bool:
    events.push("intervals:{t}")
    domain = xh_domain
    high = xh_high
    xh_known
xh_path_key_host = (n: int) -> str:
    events.push("path-key:{n}")
    xh_key
xh_refined_host = (arm: int, domain: int[], st: int, high: int[]): events.push("refined:{arm}:{domain}:{st}:{high}")
xh_string_patterns_host = (arm: int, st: int, covered: str[], lits: str[]): events.push("string-patterns:{arm}:{st}:{covered}:{lits}")
xh_ident_host = (l: int, pos: int) -> int:
    n = node(.ident); nodes[n].sym = i32(l); nodes[n].type = locals[l].type
    events.push("ident:{l}:{n}")
    n
xh_bare_host = (pos: int, name: int): events.push("bare:{pos}:{name}")
xh_catch_all_host = (l: int, st: int, seen: bool[], finite: int, ms: int[], pos: int) -> int:
    events.push("catch-all:{l}:{st}:{seen}:{finite}:{ms}")
    node(.ident)
xh_family_host = (t: int, u: int) -> int:
    events.push("family:{t}:{u}")
    0
xh_within_host = (a: int, b: int) -> bool:
    events.push("within:{a}:{b}")
    xh_within
xh_target_host = (n: int, t: int, u: int) -> int:
    events.push("target:{n}:{t}:{u}")
    xh_target
xh_literal_seen_host = (p: int, e: int, vi: int, pt: int, lits: mut str[], seen: mut bool[]):
    events.push("literal-seen:{p}:{vi}:{pt}")
    lits.push("{vi}")
    seen[vi] = true
xh_wrap_host = (n: int, t: int): events.push("wrap:{n}:{t}")
xh_union_part_host = (e: int, u: int, keep: int[], pos: int) -> int:
    events.push("union-part:{e}:{u}:{keep}")
    e
xh_none_name_host = () -> int:
    events.push("none-name")
    xh_none_id
xh_narrow_local_host = (l: int, ms: int[], pos: int):
    events.push("narrow-local:{l}:{ms}")
    xh_scope.names.push(l)
xh_opt_wild_host = (l: int, st: int, ms: int[], none_seen: bool, pos: int): events.push("opt-wild:{l}:{st}:{ms}:{none_seen}")
xh_opt_wild_path_host = (sc: int, key: str, st: int, ms: int[], none_seen: bool, pos: int): events.push("opt-wild-path:{sc}:{key}:{ms}:{none_seen}")
xh_narrow_path_host = (sc: int, ms: int[], pos: int, key: str): events.push("narrow-path:{sc}:{ms}:{key}")
# A body's ival: 1 logs a narrowing write.
xh_block_host = (b: int, expected: int, value: bool, jumps: mut int) -> int:
    jumps = 3
    events.push("block:{b}:{expected}:{value}:{xh_scope.names.len()}")
    if nodes[b].ival & 1 != 0: xh_log.push(5)
    int(nodes[b].type)
xh_returned_host = (changes: int, jumps: int, body: int): events.push("returned:{changes}:{jumps}:{body}")
xh_reset_host = (mark: int):
    events.push("reset:{mark}")
    xh_scope.names.truncate(mark)
xh_restore_host = (changes: int) -> int[]:
    events.push("restore:{changes}")
    out: int[]
    loop i in [changes..xh_log.len()): out.push(xh_log[i])
    xh_log.truncate(changes)
    out
xh_merge_host = (changed: int[]): events.push("merge:{changed}")
xh_sink_host = (m: int, b: int): events.push("sink:{m}:{b}")
xh_hint_host = (on: bool): events.push("hint:{on}")
xh_join_host = (a: int, b: int, pos: int) -> int:
    events.push("join:{a}:{b}")
    T_FLOAT
xh_string_domain_host = (m: int) -> bool: xh_string_domain
xh_int_domain_host = (m: int, covered: int[]) -> bool:
    events.push("int-domain:{covered}")
    xh_int_domain
xh_member_arms_host = (arms: int[], t: int): events.push("member-arms:{arms}:{t}")
xh_enum_missing_host = (m: int, st: int, seen: bool[], lits: str[]):
    print(events)
    print("missing:{seen}:{lits}:21")
    exit(19)
xh_string_missing_host = (m: int): events.push("string-missing:{m}")
xh_optional_missing_host = (m: int, st: int, finite: int, ms: int[]):
    print(events)
    print("optional:{finite}:{ms}:22")
    exit(19)
xh_error_host = (n: int, code: int, a: int, b: int, text: str):
    print(events)
    print("error:{n}:{a}:{b}:{text}:{code}")
    exit(19)
xh_services = CheckerMatchHost(xh_check_host, xh_finalize_host, xh_coerce_host, xh_check_to_host, xh_binding_host, xh_fields_host, xh_intervals_host, xh_path_key_host, xh_refined_host, xh_string_patterns_host, xh_ident_host, xh_bare_host, xh_catch_all_host, xh_family_host, xh_within_host, xh_target_host, xh_literal_seen_host, xh_wrap_host, xh_union_part_host, xh_none_name_host, xh_narrow_local_host, xh_opt_wild_host, xh_opt_wild_path_host, xh_narrow_path_host, xh_block_host, xh_returned_host, xh_reset_host, xh_restore_host, xh_merge_host, xh_sink_host, xh_hint_host, xh_join_host, xh_string_domain_host, xh_int_domain_host, xh_member_arms_host, xh_enum_missing_host, xh_string_missing_host, xh_optional_missing_host, xh_error_host)
xh_inputs = CheckerMatchInput(&nodes, &lists, &types, &structs, &fields, &variants, &args, &files, &locals, &names, &sets, &xh_scope, &xh_log, &xh_path_count, &xh_sink_at, &T_VOID, &T_BOOL, &T_STR, &T_MATH_INT, &T_NONE, &T_NEVER, &xh_services)
xh_binding = checker_match_bind(&xh_inputs)
DEWY = 1 << 40
value = (t: int, k: NK = .ident) -> int:
    n = node(k); nodes[n].type = i32(t); n
body = (t: int, bits: int = 0, valued: bool = true) -> int:
    b = node(.block, 0, bits, 0, [node(.exprstmt, value(t))]); nodes[b].type = i32(t)
    if valued: nodes[b].aux = 1
    b
arm = (patterns: int[], b: int) -> int:
    a = node(.arm, 0, 0, 0, patterns); nodes[a].b = i32(b); a
ptype = (t: int, name: int = 0) -> int:
    p = node(.ptype, node(.tname, 0, t, 3)); nodes[p].name = i32(name); p
plit = (e: int, name: int = 0) -> int:
    p = node(.plit, e); nodes[p].name = i32(name); p
lit = (k: NK, t: int, v: int = 0) -> int:
    n = value(t, k); nodes[n].ival = v; n
wild = (name: int = 0) -> int:
    p = node(.pwild); nodes[p].name = i32(name); p
variant = (name: int, binds: int[] = []) -> int:
    p = node(.pvariant, 0, 0, 0, binds); nodes[p].name = i32(name); p
prange = (lo: int, hi: int, inclusive: bool = true) -> int:
    p = node(.prange, lo); nodes[p].b = i32(hi)
    if inclusive: nodes[p].flags = i32(2)
    p
match_of = (subject: int, arms: int[], stmt: bool = false, dewy: bool = true) -> int:
    m = node(.match_, subject, 0, 0, arms)
    if stmt: nodes[m].flags = i32(16)
    if dewy: nodes[m].pos = DEWY + m
    m
local_subject = (t: int) -> int:
    locals.push(Local(type = i32(t)))
    s = value(t); nodes[s].aux = 1; nodes[s].sym = i32(locals.len() - 1); s
enum_type = (vnames: int[], union_types: int[] = []) -> int:
    first = variants.len()
    loop i in [0..vnames.len()):
        fs = fields.len()
        nf = 0
        if union_types.len() > 0:
            fields.push(Field(type = i32(union_types[i]))); nf = 1
        variants.push(Variant(name = i32(vnames[i]), fields = i32(fs), nfields = i32(nf)))
    ta = args.len()
    loop t in union_types: args.push(i32(t))
    structs.push(StructInfo(variants = i32(first), nvariants = i32(vnames.len()), union_ = union_types.len() > 0, targs = i32(ta), ntargs = i32(union_types.len()), resolved = union_types.len() > 0))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    types.len() - 1
run = (m: int, expected: int = 0):
    t = xh_match(m, expected)
    print("{m}:{t}:{nodes[m].aux2}:{nodes[m].sym}:{xh_scope.names}:{xh_path_count}")
prepare_match = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
    names = ["", "_", "a", "b", "c", "d", "e"]
'''

MAIN = r'''
main = ():
    prepare_match()
    # Enums: variants, a none variant, every one seen; a field-holding variant with bindings.
    color = enum_type([11, 12, 61])
    xh_grow = true
    run(match_of(value(color), [arm([variant(11)], body(T_INT)), arm([variant(12), plit(lit(.none_lit, T_NONE))], body(T_INT))]), T_INT)
    run(match_of(value(color), [arm([variant(11)], body(T_VOID, 0, false)), arm([wild()], body(T_VOID, 0, false))], true))
    # Unions: member types with bindings narrow; a subset; the rest by a wildcard.
    u = enum_type([21, 22, 23], [T_INT, T_STR, T_BOOL])
    s = local_subject(u)
    run(match_of(s, [arm([ptype(T_INT, 2)], body(T_INT)), arm([ptype(T_STR, 3)], body(T_FLOAT, 1)), arm([wild(4)], body(T_INT))]))
    sub = enum_type([31, 32], [T_STR, T_BOOL]); args.push(0)
    xh_within = true
    run(match_of(local_subject(u), [arm([ptype(T_INT)], body(T_INT)), arm([ptype(sub, 5)], body(T_INT))]), T_INT)
    xh_within = false
    run(match_of(local_subject(u), [arm([ptype(u, 2)], body(T_INT))]))
    # Union literals: a member's value, booleans together cover bool.
    xh_target = 2
    run(match_of(local_subject(u), [arm([plit(lit(.bool_lit, T_BOOL, 1))], body(T_INT)), arm([plit(lit(.bool_lit, T_BOOL, 0), 6)], body(T_INT)), arm([wild()], body(T_INT))]))
    # Field paths are narrowed through their key.
    xh_key = "p.q"
    run(match_of(value(u), [arm([ptype(T_INT)], body(T_INT)), arm([wild()], body(T_INT))]))
    xh_key = ""
    # Optionals: the payload, none, the rest; optional unions by member.
    opt = int(tb_mk_opt(T_INT))
    run(match_of(local_subject(opt), [arm([ptype(T_INT, 2)], body(T_INT)), arm([plit(lit(.none_lit, T_NONE))], body(T_INT))]), T_INT)
    run(match_of(local_subject(opt), [arm([plit(lit(.none_lit, T_NONE))], body(T_INT)), arm([wild()], body(T_INT))]))
    ou = int(tb_mk_opt(u))
    run(match_of(local_subject(ou), [arm([ptype(T_INT, 2)], body(T_INT)), arm([ptype(T_STR)], body(T_INT)), arm([wild(3)], body(T_INT))]))
    xh_target = 1
    run(match_of(local_subject(ou), [arm([plit(lit(.str_lit, T_STR), 2)], body(T_INT)), arm([wild()], body(T_INT))]))
    # Booleans; integer domains with ranges; the semantic integer's domain proof.
    run(match_of(value(T_BOOL), [arm([plit(lit(.bool_lit, T_BOOL, 1))], body(T_INT)), arm([plit(lit(.bool_lit, T_BOOL, 0))], body(T_STR))]))
    xh_known = true
    xh_domain = [0, 9]
    run(match_of(value(T_INT), [arm([plit(lit(.int_lit, T_INT, 0))], body(T_INT)), arm([prange(lit(.int_lit, T_INT, 1), lit(.int_lit, T_INT, 9))], body(T_INT))]))
    xh_high = [5]
    run(match_of(value(T_INT), [arm([prange(lit(.int_lit, T_INT, 1), lit(.int_lit, T_INT, 9), false)], body(T_INT)), arm([wild()], body(T_INT))]))
    xh_known = false
    xh_high = []
    xh_int_domain = true
    run(match_of(value(T_MATH_INT), [arm([plit(lit(.int_lit, T_MATH_INT, 3))], body(T_INT))]))
    xh_int_domain = false
    # String sets: dotname literals cover members.
    sets = [[], ["go", "stop"]]
    structs.push(StructInfo(lit_set = 1, resolved = true, nvariants = 2, variants = i32(variants.len())))
    variants.push(Variant(name = 41)); variants.push(Variant(name = 42))
    types.push(TypeInfo(kind = .enum_, st = i32(structs.len() - 1)))
    word = types.len() - 1
    go = lit(.dotname, word); nodes[go].aux = 0
    stop = lit(.dotname, word); nodes[stop].aux = 1
    run(match_of(value(word), [arm([plit(go)], body(T_INT)), arm([plit(stop)], body(T_INT))]))
    # Strings: a domain proof or a wildcard; sinks and void arms.
    xh_string_domain = true
    run(match_of(value(T_STR), [arm([plit(lit(.str_lit, T_STR))], body(T_INT))]))
    xh_string_domain = false
    m = match_of(value(T_BOOL), [arm([plit(lit(.bool_lit, T_BOOL, 1))], body(T_VOID, 0, false)), arm([wild()], body(T_INT))])
    xh_sink_at = m
    run(m)
    run(match_of(value(T_BOOL), [arm([plit(lit(.bool_lit, T_BOOL, 1))], body(T_NEVER)), arm([wild()], body(T_NEVER))]))
    # Variants with field bindings; `_` skips one.
    rec = enum_type([51, 52], [T_INT, T_STR])
    b1 = node(.ident); nodes[b1].name = 2
    b2 = node(.ident); nodes[b2].name = 1
    run(match_of(value(rec), [arm([variant(51, [b1])], body(T_INT)), arm([variant(52, [b2])], body(T_INT))]))
    print(locals.len())
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_match_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('intervals', 'checker_match')).endswith(b'ok\n')


@pytest.mark.parametrize('case,code', [
    ('run(match_of(value(T_INT), [arm([wild()], body(T_INT)), arm([wild()], body(T_INT))]))', 1),
    ('u = enum_type([21, 22], [T_INT, T_STR]); run(match_of(value(u), [arm([ptype(T_BOOL)], body(T_INT))]))', 2),
    ('u = enum_type([21, 22], [T_INT, T_STR]); xh_target = -1; run(match_of(value(u), [arm([plit(lit(.int_lit, T_INT))], body(T_INT))]))', 3),
    ('u = enum_type([21, 22], [T_INT, T_FLOAT]); xh_target = 1; run(match_of(value(u), [arm([plit(lit(.float_lit, T_FLOAT))], body(T_INT))]))', 4),
    ('c = enum_type([11, 12]); run(match_of(value(c), [arm([variant(13)], body(T_INT))]))', 5),
    ('u = enum_type([21, 22], [T_INT, T_STR]); run(match_of(value(u), [arm([ptype(T_INT)], body(T_INT)), arm([variant(21)], body(T_INT))]))', 6),
    ('u = enum_type([21, 22], [T_INT, T_STR]); run(match_of(value(u), [arm([variant(21, [node(.ident), node(.ident)])], body(T_INT))]))', 7),
    ('u = enum_type([21, 22], [T_INT, T_STR]); run(match_of(value(u), [arm([variant(21, [node(.ident)]), variant(22)], body(T_INT))]))', 8),
    ('p = variant(21); nodes[p].aux = 1; run(match_of(value(T_INT), [arm([p], body(T_INT))]))', 9),
    ('run(match_of(value(T_STR), [arm([prange(lit(.int_lit, T_INT), lit(.int_lit, T_INT))], body(T_INT))]))', 11),
    ('run(match_of(value(T_INT), [arm([node(.pshape)], body(T_INT))]))', 12),
    ('xh_known = true; xh_domain = [0, 9]; run(match_of(value(T_INT), [arm([plit(lit(.int_lit, T_INT, 2))], body(T_INT)), arm([plit(lit(.int_lit, T_INT, 2))], body(T_INT))]))', 13),
    ('run(match_of(value(T_BOOL), [arm([plit(lit(.bool_lit, T_BOOL, 1))], body(T_INT)), arm([plit(lit(.bool_lit, T_BOOL, 0))], body(T_VOID, 0, false))]), T_INT)', 14),
    ('xh_known = true; xh_domain = [0, 9]; run(match_of(value(T_INT), [arm([plit(lit(.int_lit, T_INT, 2))], body(T_INT))]))', 15),
    ('run(match_of(value(T_INT), [arm([plit(lit(.int_lit, T_INT, 2))], body(T_INT))]))', 20),
    ('run(match_of(value(T_INT), [arm([plit(lit(.int_lit, T_INT, 2))], body(T_INT))], false, false))', 20),
    ('c = enum_type([11, 12]); run(match_of(value(c), [arm([variant(11)], body(T_INT))]))', 21),
    ('run(match_of(value(int(tb_mk_opt(T_INT))), [arm([plit(lit(.none_lit, T_NONE))], body(T_INT))]))', 22),
])
def test_checker_match_errors(compiler, tmp_path, case, code):  # noqa: F811
    main = f'''
main = ():
    prepare_match()
    {case}
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('intervals', 'checker_match'))
    assert output.rstrip().endswith(f':{code}'.encode())
