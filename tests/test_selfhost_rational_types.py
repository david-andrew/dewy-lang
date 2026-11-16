"""Bundled rational identity keeps pruning, packed positions and source ownership."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401

SERVICES = '''use 'checker_types.dewy'
struct RNode:
    pos: int = 0
struct RFile:
    path: str = ""
types: TypeInfo[]
structs: StructInfo[]
nodes: RNode[]
files: RFile[]
lib_dir = "/lib"
prunes = 0
positions = 0
prune = (t: int) -> int:
    prunes += 1
    if t == 12: 2 else: t
pos_file = (p: int) -> int:
    positions += 1
    p >> 40
'''
DRIVER = '''main = ():
    files = [RFile("/shadow/rational.dewy"), RFile("/lib/rational.dewy"), RFile("/lib/rational.dewy.more"), RFile("/unicode/α/rational.dewy")]
    nodes = [RNode(), RNode((1 << 40) | 0xFFFFFFFFFF), RNode(5), RNode((2 << 40) | 7), RNode((3 << 40) | 9)]
    structs = [StructInfo(), StructInfo(decl=1, name="RationalWord"), StructInfo(decl=1, name="Rational"), StructInfo(decl=2, name="RationalWord"), StructInfo(decl=3, name="Rational"), StructInfo(decl=0, name="Rational"), StructInfo(decl=0, name="RationalWord"), StructInfo(decl=999999, name="Other"), StructInfo(decl=4, name="Rational")]
    types = [TypeInfo(st=999999)]
    loop i in [1..9): types.push(TypeInfo(kind=.struct_, st=i32(i)))
    types.push(TypeInfo(st=999999))
    # Wrong kind/name/zero declaration must not dereference poisoned indices.
    loop i in [0..10): print("{i} {bundled_word_rational_type(i)} {bundled_rational_type(i)}")
    print("counts {prunes} {positions}")
    print("alias {bundled_word_rational_type(12)} {bundled_rational_type(12)}")
    structs[1].name = "Other"
    print("renamed {bundled_word_rational_type(1)}")
    structs[1].name = "RationalWord"
    print("restored {bundled_word_rational_type(1)}")
    lib_dir = "/unicode/α"
    print("relocated {bundled_rational_type(8)}")
    held = files
    files[3].path += ".more"
    print("changed {bundled_rational_type(8)} held {held[3].path}")
    print("final {prunes} {positions}")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_rational_types_matches_twin(compiler, tmp_path, release):
    output = compare_narrow(
        compiler, tmp_path, release, ('checker_types', 'rational_types'), DRIVER,
        doubles={'services.jo': SERVICES, 'units.jo': "use 'services.jo'\n"},
        services=('ast', 'check', 'types', 'util'))
    assert output.decode().splitlines() == [
        '0 false false', '1 true false', '2 false true',
        '3 false false', '4 false false', '5 false false',
        '6 false false', '7 false false', '8 false false', '9 false false',
        'counts 20 5', 'alias false true', 'renamed false', 'restored true',
        'relocated true', 'changed false held /unicode/α/rational.dewy',
        'final 26 9',
    ]


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_rational_types_programs_match_twin(compiler, tmp_path, monkeypatch, release):
    cases = ['rational/builtin', 'rational/word', 'rational/mixed', 'rational/library_name', 'rational/library_word_name', 'units/conversions', 'units/functions',
             'units/formatting', 'units/dimensioned_power',
             'default_proofs/unit_decimal_float_named']
    assert all((ROOT / 'tests/cases' / (case + '.dewy')).is_file() for case in cases)
    # Compile real programs through a compiler pair differing only in this leaf.
    assert compare_facts(compiler, tmp_path, monkeypatch, cases,
                         flags=('--release',) if release else (), leaves=('rational_types',)) > 0
