"""Full and partial generic substitution match the frozen recursive owner."""
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_constructors import DRIVER as CONSTRUCTOR_DRIVER

DRIVER = CONSTRUCTOR_DRIVER.split('main = ():')[0] + r'''
substitution_binding = type_substitute_bind(&inference_input)
grow = false
maybe_grow = ():
    if not grow: return
    grow = false
    loop i in [0..160]:
        types.push(TypeInfo(kind=.bool_))
        structs.push(StructInfo())
        args.push(0)
    assert(ts_subst(T_INT, []) == T_INT, "reentrant concrete substitution")
sub_effect = (id: int, values: int[], zonking: bool) -> int:
    assert(not zonking)
    maybe_grow()
    events.push("effect:{id}:{values}")
    id + 100
sub_ref = (id: int, values: int[], zonking: bool) -> int:
    assert(not zonking)
    maybe_grow()
    events.push("ref:{id}:{values}")
    id + 200
make_effect = (id: int) -> int:
    maybe_grow()
    t = TypeInfo(kind=.effect, st=i32(id))
    type_intern(&t, [])
make_callable = (elem: int, effect: int, bits: int) -> int:
    maybe_grow()
    t = TypeInfo(kind=.callable, elem=i32(elem), st=i32(effect), bits=i32(bits))
    type_intern(&t, [])
make_refined = (elem: int, ref: int) -> int:
    maybe_grow()
    t = TypeInfo(kind=.refined, elem=i32(elem), st=i32(ref))
    type_intern(&t, [])
make_quantity = (elem: int, dim: int, unit: int, bits: int) -> int:
    assert(unit == 0)
    maybe_grow()
    t = TypeInfo(kind=.quantity, elem=i32(elem), st=i32(dim), bits=i32(bits))
    type_intern(&t, [])
make_instance = (decl: int, values: int[]) -> int:
    maybe_grow()
    events.push("instance:{decl}:{values}")
    int(tb_mk_tuple(values, false))
main = ():
    inference_host = TypeInferenceHost(make_callable, sub_effect, make_effect, make_refined, sub_ref, make_quantity, make_instance, unused_make, unused_union)
    loop word in [8, 4]:
        types = [TypeInfo()]; args = []; table = []; structs = []
        binds = 0; var_counter = 0; secrets_seen = false; values_any = false
        events = []; ptr_size = word
        tb_init_types()
        p = int(tb_mk_param(0)); q = int(tb_mk_param(1))
        assert(ts_subst(0, []) == 0 and ts_subst(T_INT, []) == T_INT)
        assert(ts_subst(p, []) == p and ts_subst(q, [T_INT, 0]) == q)
        assert(ts_subst(p, [T_INT]) == T_INT)
        v = int(tb_mk_var())
        assert(ts_subst(v, [T_INT]) == v)
        types[v].ref = i32(p)
        assert(ts_subst(v, [T_INT]) == T_INT)
        a = int(tb_mk_array(p)); b = int(tb_mk_ptr(q))
        nested = int(tb_mk_opt(tb_mk_fixed(tb_mk_secret(a), 7)))
        pair = int(tb_mk_tuple([nested, b, p], true))
        fn = int(tb_mk_fn([pair, p], q, 3, 41, 29, true))
        cf = int(tb_mk_cfn([p, q], a))
        bound = [T_INT, T_STR]
        saved_types = types; saved_args = args
        reenter = true
        result = int(ts_subst(fn, bound))
        assert(not reenter and types[result].kind == .fn_)
        assert(types[result].elem == i32(T_STR) and types[result].mutmask == 3 and types[result].st == 41 and types[result].bits == 0 and types[result].sign)
        assert(tu_targ(result, 1) == T_INT)
        cp = int(ts_subst(cf, bound))
        assert(types[cp].kind == .cfn and tu_targ(cp, 1) == T_STR)
        assert(types[int(types[cp].elem)].elem == i32(T_INT))
        partial = [0, T_STR]
        before = partial
        pr = int(ts_partial(fn, partial))
        assert(partial[0] != 0 and before[0] == 0 and types[partial[0]].kind == .var)
        assert(tu_targ(pr, 1) == partial[0] and types[pr].elem == i32(T_STR))
        assert(ts_partial(p, partial) == partial[0])
        assert(ts_partial(cf, partial) == cf, "partial C functions retain the existing policy")
        assert(saved_types.len() < types.len() and saved_args.len() < args.len())
        ef = TypeInfo(kind=.effect, st=5, flags=1)
        types.push(ef); effect = types.len() - 1
        assert(ts_partial(effect, partial) == effect)
        grow = true
        es = int(ts_subst(effect, bound))
        assert(not grow and types[es].st == 105)
        ca = make_callable(p, 7, 13)
        rf = make_refined(p, 9)
        qu = make_quantity(p, 11, 0, 17)
        loop t in [ca, rf, qu]:
            old = types
            grow = true
            out = int(ts_subst(t, bound))
            assert(not grow and types.len() > old.len())
            assert(types[out].elem == i32(T_INT))
            grow = true
            out = int(ts_partial(t, partial))
            assert(not grow and types[out].elem == i32(partial[0]))
        loop kind in [TK.struct_, TK.enum_]:
            first = args.len(); args.push(i32(p)); args.push(i32(q))
            si = structs.len(); structs.push(StructInfo(decl=91, targs=i32(first), ntargs=2))
            types.push(TypeInfo(kind=kind, st=i32(si), flags=1)); nominal = types.len() - 1
            grow = true
            out = int(ts_subst(nominal, bound))
            assert(not grow and tu_targ(out, 0) == T_INT and tu_targ(out, 1) == T_STR)
            grow = true
            out = int(ts_partial(nominal, partial))
            assert(not grow and tu_targ(out, 0) == partial[0])
        print("{result}:{cp}:{pr}:{partial}")
        print(events)
        print(args)
    print("ok")
'''
@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_substitute_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_constructors', 'type_substitute')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
