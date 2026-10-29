"""Union membership, literal-set holders and compilation-local alias publication."""
import subprocess
import pytest
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_type_unions import DRIVER as CONSTRUCTION_DRIVER

DRIVER = CONSTRUCTION_DRIVER[:CONSTRUCTION_DRIVER.index('main = ():')]
DRIVER = DRIVER.replace('literal_of = (t0: int) -> int:\n', 'lookup_grow = false\nlookup_union = 0\nliteral_of = (t0: int) -> int:\n    if lookup_grow:\n        lookup_grow = false\n        loop i in [0..128):\n            types.push(TypeInfo())\n            structs.push(StructInfo())\n            args.push(0)\n            sets.push([])\n        assert(uu_index(lookup_union, 1) == 0, "reentrant member lookup")\n')
DRIVER += r'''
main = ():
    loop round in [0..2):
        union_reset()
        u: int = int(uu_mk_union([1, 2]))
        assert(uu_index(u, 1) == 0 and uu_index(u, 2) == 1 and uu_index(u, 3) == -1)
        lookup_union = u
        linked = types.len()
        types.push(TypeInfo(kind=.var, ref=i32(u)))
        member = types.len()
        types.push(TypeInfo(kind=.var, ref=1))
        assert(uu_index(linked, member) == 0)
        a = make_kind(.array, 4, 0, 0)
        b = make_kind(.array, 5, 0, 0)
        pending: int = int(uu_mk_union([a, 3]))
        assert(uu_index(pending, b) == -1)
        assert(tu_unify(4, 1) and tu_unify(5, 1))
        assert(uu_index(pending, b) == 1, "structural equality after inference")
        one = literal(["alpha"])
        both = literal(["alpha", "beta"])
        miss = literal(["alpha", "gamma"])
        mixed: int = int(uu_mk_union([1, both]))
        assert(uu_holder(mixed, one, true) == 1)
        assert(uu_holder(mixed, miss, false) == 1)
        assert(uu_holder(mixed, miss, true) == -1)
        assert(uu_holder(mixed, 2, false) == -1)
        assert(uu_holder(mixed, both, true) == 1)
        old_types = types
        old_sets = sets
        old_args = args
        lookup_grow = true
        assert(uu_holder(mixed, one, true) == 1 and not lookup_grow)
        assert(types.len() == old_types.len() + 128 and sets.len() == old_sets.len() + 128)
        assert(args.len() == old_args.len() + 128)
        assert(uu_alias_name(u) == 0)
        uu_alias_note(linked, 17)
        assert(uu_alias_name(u) == 17 and uu_alias_name(linked) == 17)
        uu_alias_note(u, 17)
        assert(uu_alias_name(u) == 17)
        uu_alias_note(u, 18)
        uu_alias_note(u, 17)
        assert(uu_alias_name(u) == 0, "ambiguity stays cached")
        uu_alias_note(1, 99)
        assert(uu_alias_name(1) == 0)
        uu_alias_note(mixed, 22)
        assert(uu_alias_name(mixed) == 22)
        print("members:{uu_index(linked, member)}:{uu_index(pending, b)}:{uu_holder(mixed, one, true)}")
        print("aliases:{uu_alias_name(u)}:{uu_alias_name(mixed)}:{uu_alias_name(1)}")
        type_union_bind(&union_input)
        assert(uu_alias_name(mixed) == 0, "new compilation has no stale alias")
    print("ok")
'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_union_lookup_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('checker_types', 'checker_tokens', 'refinement_types', 'refine_predicates', 'refine_queries', 'type_queries', 'type_intern', 'type_inference', 'type_unions')
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
