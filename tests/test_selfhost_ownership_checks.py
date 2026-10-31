"""Ownership diagnostics (ownership_checks) match their frozen Jo twin."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_ownership_types import DRIVER as TYPES, STEMS as TYPE_STEMS

STEMS = ('node_store', 'source_types') + TYPE_STEMS + ('ownership_checks',)

DRIVER = TYPES.split('\nmain = ():')[0] + r'''
nodes: Node[] = [Node()]
lists: i32[]
locals: Local[] = [Local()]
globals: Global[] = [Global()]
files: SrcFile[] = [SrcFile(is_dewy=true), SrcFile()]
oc_names: str[] = ["", "x", "$guard1", "y"]
hooks: {int: int} = {}
functions: {int: bool} = {}
inputs: {int: bool} = {}
bindings: {int: bool} = {}
oc_events: str[]
no_escape: int[]
oc_error = (pos: int, message: str):
    print(oc_events)
    print("error:{pos}:{message}")
    exit(23)
oc_escapes = (body: int, l: int) -> bool:
    oc_events.push("escapes:{body}:{l}")
    if not grew:
        grow()
        loop i in [0..64): nodes.push(Node()); locals.push(Local()); fns.push(FnInst()); lists.push(0)
    not no_escape.contains(l)
oc_contract = (t: int) -> int:
    oc_events.push("contract:{t}")
    5
oc_callable = (t: int, contract: int, cap: int) -> int:
    oc_events.push("callable:{t}:{contract}:{cap}")
    t + 1000
oc_host = OwnershipCheckHost(oc_error, oc_escapes, oc_contract, oc_callable)
oc_input = OwnershipCheckInput(&nodes, &lists, &types, &structs, &fields, &locals, &globals, &fns, &files, &oc_names, &decls, &hooks, &functions, &inputs, &bindings, 11, 12, 13, 14, 1, &oc_host)
oc_binding = ownership_checks_bind(&oc_input)
mk = (k: NK, t: int = 0, kids: int[] = []) -> int:
    start = lists.len()
    loop c in kids: lists.push(i32(c))
    nodes.push(Node(kind=k, type=i32(t), list=i32(start), nlist=i32(kids.len()), pos=nodes.len() * 10))
    nodes.len() - 1
local = (t: int, flags: int = 0, name: int = 1) -> int:
    locals.push(Local(type=i32(t), flags=i32(flags), name=i32(name), pos=locals.len() * 100))
    locals.len() - 1
function = (body: int, ls: int[], ps: int[] = [], file: int = 0) -> int:
    decl = mk(.fn_)
    nodes[decl].pos = (file << 40) + decl
    fns.push(FnInst(body=i32(body), decl=i32(decl), locals=ls, params=ps))
    fns.len() - 1
ident = (l: int) -> int:
    n = mk(.ident, int(locals[l].type))
    nodes[n].sym = i32(l); nodes[n].aux = 1
    n
prepare = () -> int:
    reset()
    fields = []
    variants = []
    params = []
    types[1].size = 8; types[1].align = 8; types[1].flags = 2
    types[2].size = 8; types[2].align = 8; types[2].flags = 6
    types[3].size = 1; types[3].align = 1; types[3].flags = 2
    type_format_bind(&format_input)
    type_layout_bind(&layout_input)
    type_property_bind(&property_input)
    math_id = add(TypeInfo(kind=.int_, rep=.tagged_int, size=8, align=8, flags=2))
    res = nominal("Res", 50, [1])
    structs[int(types[res].st)].drop_fn = 7
    decls[50 * 4 + 1] = 1
    res
'''

MAIN = r'''
main = ():
    res = prepare()
    cop = nominal("Cop", 60, [1])
    hook = fns.len()
    fns.push(FnInst(ret=i32(cop)))
    decls[60 * 4 + 2] = hook
    copies[cop] = hook
    arr_res = kind(.array, res)
    fix_cop = kind(.fixed, cop, 2)
    holder = nominal("Holder", 0, [res, kind(.opt, res)])
    # Dewy parameter bindings adopt their incoming owner; a mutable one does not.
    p = local(res, 524288)
    q = local(res, 2)
    b = local(res)
    c = local(res)
    plain = local(1)
    bind_b = mk(.vardecl, 0); nodes[bind_b].aux2 = 1; nodes[bind_b].sym = i32(b); nodes[bind_b].b = i32(ident(p))
    bind_c = mk(.vardecl, 0); nodes[bind_c].aux2 = 1; nodes[bind_c].sym = i32(c); nodes[bind_c].b = i32(ident(q))
    first = mk(.exprstmt)
    # A body over the walked kinds: construction, growable arrays, conversions.
    ctor = mk(.call, holder, [ident(b), 0]); nodes[ctor].aux = 2
    copy = mk(.conv, cop, [])
    nodes[copy].aux = 14; nodes[copy].a = i32(mk(.ident, cop))
    rep = mk(.array, fix_cop, [mk(.ident, cop)]); nodes[rep].b = i32(mk(.int_lit, 1))
    target = mk(.index, res); nodes[target].a = i32(mk(.ident, arr_res))
    assign = mk(.assign, 0); nodes[assign].a = i32(target); nodes[assign].b = i32(ident(c))
    grow_call = mk(.intrinsic, 0, [mk(.ident, arr_res)]); nodes[grow_call].aux = 3
    cond = mk(.if_, 0); nodes[cond].a = i32(mk(.bool_lit, 3)); nodes[cond].b = i32(mk(.block, 0, [mk(.exprstmt, 0)])); nodes[cond].c = i32(mk(.block, 0, [mk(.return_)]))
    lam = mk(.lambda, res, [mk(.call, res)])
    made = mk(.exprstmt, holder); nodes[made].a = i32(ctor)
    blk = mk(.block, 0, [bind_b, bind_c, first, made, copy, rep, assign, grow_call, cond, lam])
    f1 = function(blk, [p, q, b, c, plain], [p, q])
    f2 = function(mk(.block, 0, [mk(.defer_, 0)]), [plain])
    lp = local(res, 0, 3)
    lib = function(mk(.block, 0, [mk(.return_)]), [lp], [lp], 1)
    lq = local(res)
    no_escape.push(lq)
    lib2 = function(mk(.block), [lq], [lq], 1)
    ownership_parameters()
    print(functions)
    print(inputs)
    print(bindings)
    ownership_validate()
    # Closure capabilities: copyable, move-only, borrowed; none without hooks.
    cap_fn = function(0, [])
    v1 = local(cop, 262144)
    v2 = local(res, 262144)
    v3 = local(res, 8388608)
    fns[cap_fn].caps = [Capture(inner=i32(v1))]
    print(ownership_lambda_type(77, cap_fn))
    fns[cap_fn].caps = [Capture(inner=i32(v1)), Capture(inner=i32(v2))]
    print(ownership_lambda_type(78, cap_fn))
    fns[cap_fn].caps = [Capture(inner=i32(v3))]
    print(ownership_lambda_type(79, cap_fn))
    fns[cap_fn].caps = [Capture(inner=i32(plain))]
    print(ownership_lambda_type(80, cap_fn))
    print(oc_events)
    print(contained)
    decls.clear()
    ownership_parameters()
    ownership_validate()
    print(ownership_lambda_type(81, cap_fn))
    print("ok")
'''


def run(compiler, tmp_path, release, driver, status=0):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in STEMS:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in STEMS) + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_ownership_checks_twins(compiler, tmp_path, release):  # noqa: F811
    output = run(compiler, tmp_path, release, DRIVER + MAIN)
    assert output.endswith(b'ok\n')
    assert b'callable:78:5:2' in output and b'callable:79:5:3' in output


ERRORS = [
    ('partial', '''
    n = mk(.partial, 0, [ident(local(res))])
    function(mk(.block, 0, [mk(.exprstmt, 0, []), n]), [])
''', 'partial application of owners'),
    ('fixed', '''
    n = mk(.array, kind(.fixed, res, 2))
    function(n, [])
''', 'owning array elements require completed construction'),
    ('repeat', '''
    n = mk(.array, kind(.fixed, res, 2), [mk(.ident, res)])
    nodes[n].b = i32(mk(.int_lit, 1))
    function(n, [])
''', 'cannot repeat a move-only owner'),
    ('arrdata', '''
    n = mk(.intrinsic, 0, [mk(.ident, kind(.array, res))]); nodes[n].aux = 11
    function(n, [])
''', 'live-slot protocol'),
    ('setlen', '''
    n = mk(.intrinsic, 0, [mk(.ident, kind(.array, res))]); nodes[n].aux = 13
    function(n, [])
''', 'use push'),
    ('hook', '''
    h = function(0, [])
    hooks[int(fns[h].decl)] = 1
    n = mk(.call, 0); nodes[n].sym = i32(h)
    function(n, [])
''', 'lifecycle hooks are compiler-only'),
    ('fnref', '''
    g = function(0, [local(res)])
    n = mk(.fnref, 0); nodes[n].sym = i32(g)
    function(n, [])
    ownership_parameters()
''', 'owners require direct calls'),
    ('record', '''
    h = nominal("Holder", 0, [res])
    n = mk(.call, h, [0]); nodes[n].aux = 2
    function(n, [])
''', 'an owning field requires completed construction'),
    ('vardecl', '''
    n = mk(.vardecl, 0); nodes[n].sym = i32(local(res))
    function(n, [])
''', 'construction before registration'),
    ('borrowed', '''
    n = mk(.assign, 0); nodes[n].a = i32(ident(local(res, 32)))
    function(n, [])
''', 'cannot replace a borrowed owner'),
    ('replace', '''
    n = mk(.assign, 0); nodes[n].a = i32(mk(.field, res))
    function(n, [])
''', 'whole local or growable array element'),
    ('defer', '''
    g = local(res, 0, 2)
    x = local(res, 0, 1)
    f = function(mk(.defer_, 0), [g, x])
    nodes[int(fns[f].body)].a = i32(mk(.block))
    ownership_parameters()
''', 'unified defer unwind plan'),
    ('copy', '''
    n = mk(.conv, res); nodes[n].aux = 14
    function(n, [])
''', 'no $__copy__ hook'),
    ('global', '''
    d = mk(.vardecl)
    globals.push(Global(type=i32(kind(.opt, res)), decl=i32(d)))
''', 'global owners require'),
    ('container', '''
    function(mk(.block), [local(kind(.tuple, 0))])
    types[types.len() - 1].nargs = 1; types[types.len() - 1].args = i32(args.len()); args.push(i32(res))
''', 'aggregate ownership support'),
    ('shared', '''
    function(mk(.block), [local(res, 1024)])
''', 'closure ownership support'),
    ('foreign', '''
    f = function(mk(.block), [local(res)])
    fns[f].cabi = true
    ownership_parameters()
''', 'per-foreign-thread cleanup storage'),
    ('closed', '''
    p = local(res)
    l = local(res)
    s = mk(.vardecl, 0); nodes[s].aux2 = 1; nodes[s].sym = i32(l); nodes[s].b = i32(ident(p))
    f = function(mk(.block, 0, [s]), [p, l])
    fns[f].has_env = true
    ownership_parameters()
''', 'owning parameters require a closed direct call'),
]


@pytest.mark.parametrize('name,body,message', ERRORS, ids=[e[0] for e in ERRORS])
def test_ownership_checks_errors(compiler, tmp_path, name, body, message):  # noqa: F811
    main = '\nmain = ():\n    res = prepare()\n' + body + '    ownership_validate()\n    print("unreachable")\n'
    output = run(compiler, tmp_path, False, DRIVER + main, status=23)
    assert message.encode() in output.splitlines()[-1], output[-400:]
