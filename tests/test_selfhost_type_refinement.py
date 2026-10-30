"""Frozen refinement construction, representation and typed-limit behavior."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_constructors import DRIVER as CONSTRUCTOR_DRIVER

DRIVER = CONSTRUCTOR_DRIVER.split('main = ():')[0] + r'''
predicates: RefAtom[][] = [[]]
active = false
spans: int[]
grow_refine = false
copy_span = (source: int, dest: int):
    spans.push(source); spans.push(dest)
    if grow_refine:
        grow_refine = false
        loop i in [0..160]: types.push(TypeInfo()); predicates.push([]); structs.push(StructInfo()); args.push(0)
        nested = int(tr_make(T_INT, 0))
        assert(types[nested].kind == .refined)
domain = (t: int, reason: FactReason, at: int) -> FactBound:
    assert(reason == .missing and at == 0 and t == T_I8)
    FactBound(-128, 127)
fits = (value: int, t: int) -> bool:
    if t == T_I8: return value >= -128 and value <= 127
    if t == T_U64: return value >= 0
    true
fail = (position: int, message: str):
    print("fatal:{position}:{message}")
    assert(false)
refine_host = TypeRefinementHost(copy_span, domain, fits, fail)
refine_binding = type_refinement_bind(&inference_input, &predicates, &active, &T_U64, &refine_host)
main = ():
    inference_host.mk_type = make
    loop word in [8, 4]:
        types = [TypeInfo()]; args = []; table = []; structs = []
        binds = 0; var_counter = 0; secrets_seen = false; values_any = false
        events = []; ptr_size = word; active = false; predicates = [[]]; spans = []
        tb_init_types()
        p = int(tb_mk_param(0)); q = int(tb_mk_param(1))
        lower = RefAtom(.ge, RefTerm(), RefTerm(1, 1))
        upper = RefAtom(.le, RefTerm(), RefTerm(1, 20))
        a = int(tr_intern([lower])); b = int(tr_intern([upper]))
        saved_types = types; saved_predicates = predicates
        grow_refine = true
        first = int(tr_make(T_INT, a))
        assert(not grow_refine and active and saved_types.len() < types.len() and saved_predicates.len() < predicates.len())
        assert(types[first].elem == i32(T_INT) and types[first].st == i32(a))
        combined = int(tr_make(first, b))
        assert(types[combined].elem == i32(T_INT) and predicates[int(types[combined].st)].len() == 2)
        again = int(tr_make(first, b))
        assert(again == combined)
        nested = int(tb_mk_tuple([int(tb_mk_array(first)), int(tb_mk_fixed(first, 5)), int(tb_mk_opt(first))], true))
        repr = int(tr_deep(nested))
        assert(types[repr].kind == .tuple and types[repr].sign)
        loop i in [0..3): assert(types[int(tu_targ(repr, i))].elem == i32(T_INT))
        assert(types[int(tu_targ(repr, 1))].bits == 5)
        ptr = int(tb_mk_ptr(first))
        assert(tr_deep(ptr) == ptr, "pointer representation policy is unchanged")
        limit = int(tr_intern([RefAtom(.le, RefTerm(), RefTerm(4, q, true))]))
        generic = int(tr_make(p, limit))
        assert(tu_has_var(generic) and tu_targ(generic, 0) == q)
        assert(tr_limit(RefTerm(4, q, true)).value == q)
        assert(tr_limit(RefTerm(4, T_U64, true)) == RefTerm(1, -1, true))
        assert(tr_limit(RefTerm(4, T_I8, true)) == RefTerm(1, 127))
        assert(tr_limit(RefTerm(4, T_I8, false)) == RefTerm(1, -128))
        length = int(tr_intern([RefAtom(.le, RefTerm(0, 0, false, [-1]), RefTerm(1, -1, true))]))
        array = int(tr_make(tb_mk_array(T_INT), length))
        normalized = predicates[int(types[array].st)][0]
        assert(normalized.b == RefTerm(1, 9223372036854775807))
        text = int(tr_make(T_STR, length))
        assert(types[text].elem == i32(T_STR))
        print("{first}:{combined}:{repr}:{generic}:{array}:{text}")
        print(spans); print(events)
    print("ok")
'''


def compare_twins(compiler, tmp_path, release, driver, status=0):
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_constructors', 'type_refinement')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_refinement_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare_twins(compiler, tmp_path, release, DRIVER).endswith(b'ok\n')


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
@pytest.mark.parametrize('expression,message', [
    ('tr_limit(RefTerm(4, T_STR, true))', 'refinement type limit requires an integer type'),
    ('tr_make(T_BOOL, 0)', 'refinement requires an integer, array or string base'),
    ('tr_make(T_I8, tr_intern([RefAtom(.le, RefTerm(), RefTerm(1, 128))]))',
     'refinement bound is outside its integer representation'),
    ('tr_make(T_I8, tr_intern([RefAtom(.le, RefTerm(), RefTerm(1, 1, true))]))',
     'refinement bound is outside its integer representation'),
], ids=['noninteger-limit', 'unsupported-base', 'signed-bound', 'unsigned-bound'])
def test_type_refinement_errors(compiler, tmp_path, release, expression, message):  # noqa: F811
    driver = DRIVER.split('main = ():')[0].replace('assert(false)', 'exit(17)')
    driver += ('main = ():\n    inference_host.mk_type = make\n    tb_init_types()\n'
               f'    {expression}\n    assert(false, "expected refinement failure")\n')
    output = compare_twins(compiler, tmp_path, release, driver, status=17)
    assert output == f'fatal:-1:{message}\n'.encode()
