"""Predicate substitution preserves type limits, spans, snapshots and zonking."""
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_constructors import DRIVER as CONSTRUCTOR_DRIVER

DRIVER = CONSTRUCTOR_DRIVER.split('main = ():')[0].replace('        reenter = false', '        reenter = false\n        loop i in [0..160]: predicates.push([])') + r'''
predicates: RefAtom[][] = [[]]
spans: int[]
span_reenter = false
copy_span = (source: int, dest: int):
    spans.push(source); spans.push(dest)
    if span_reenter:
        span_reenter = false
        empty = int(ts_ref_subst(0, [], false))
        assert(predicates[empty].len() == 0)
refinement_input = TypeSubstituteRefinements(&predicates, copy_span)
refinement_binding = type_substitute_refinements(&refinement_input)
substitution_binding = type_substitute_bind(&inference_input)
main = ():
    loop word in [8, 4]:
        types = [TypeInfo()]; args = []; table = []; structs = []
        binds = 0; var_counter = 0; secrets_seen = false; values_any = false
        events = []; ptr_size = word; predicates = [[]]; spans = []
        tb_init_types()
        p = int(tb_mk_param(0)); q = int(tb_mk_param(1))
        fn = int(tb_mk_fn([p], q, 0))
        first = RefAtom(.lt, RefTerm(4, p, true, [3, 5], 7), RefTerm(4, q, false, [2], -4))
        second = RefAtom(.gt, RefTerm(4, fn), RefTerm(1, 99, true, [8], 6))
        predicates.push([first, second]); source = predicates.len() - 1
        old = predicates
        reenter = true; span_reenter = true
        out = int(ts_ref_subst(source, [T_INT, T_STR], false))
        assert(not reenter and not span_reenter and predicates.len() > 160)
        assert(old.len() == 2 and old[source][0].a.value == p)
        a = predicates[out][1]; b = predicates[out][0]
        assert(a.a.value == T_INT and a.a.unsigned and a.a.path == [3, 5] and a.a.offset == 7)
        assert(a.b.value == T_STR and not a.b.unsigned and a.b.path == [2] and a.b.offset == -4)
        assert(types[b.a.value].kind == .fn_ and tu_targ(b.a.value, 0) == T_INT and types[b.a.value].elem == i32(T_STR))
        assert(b.b == second.b)
        assert(ts_ref_subst(source, [T_INT, T_STR], false) == out, "canonical predicate reuse")
        unbound = int(ts_ref_subst(source, [0, 0], false))
        assert(predicates[unbound][1].a.value == p, "unbound type limits stay generic")
        variable = int(tb_mk_var()); types[variable].ref = i32(T_I16)
        predicates.push([RefAtom(.eq, RefTerm(4, variable), RefTerm(1, 12))]); linked = predicates.len() - 1
        zonked = int(ts_ref_subst(linked, [], true))
        assert(predicates[zonked][0].a.value == T_I16)
        empty = int(ts_ref_subst(0, [], true))
        assert(predicates[empty].len() == 0)
        assert(spans[0] == source and spans[1] == out and spans[2] == 0 and spans[3] == empty)
        print(spans)
        loop atom in predicates[out]: print("{int(atom.op)}:{atom.a.kind}:{atom.a.value}:{atom.a.unsigned}:{atom.a.path}:{atom.a.offset}:{atom.b.kind}:{atom.b.value}:{atom.b.unsigned}:{atom.b.path}:{atom.b.offset}")
    print("ok")
'''
@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_predicate_substitute_twins(compiler, tmp_path, release):  # noqa: F811
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
