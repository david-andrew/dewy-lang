"""Storage queries keep path-local cycles and the conservative depth boundary."""
import subprocess

import pytest

from tests.support import ROOT, compiler


@pytest.mark.core_quick
def test_storage_query_paths(compiler, tmp_path):
    source = tmp_path / 'storage_walk.jo'
    source.write_text(f"use '{ROOT / 'compiler/refine.jo'}'\nuse '{ROOT / 'compiler/types.jo'}'\n" + '''
init_types()
positive = mk_type(TypeInfo(kind = .refined, elem = i32(T_INT)), [])
plain = mk_tuple([T_INT, T_STR])
assert(not ref_storage_contract(plain))
assert(ref_storage_contract(mk_tuple([plain, mk_array(positive)])))
assert(not ref_storage_contract(mk_fn([positive], positive, 0)))
# A repeated sibling is not an ancestor. Its longer route reaches the cap.
deep = plain
loop i in [0..31): deep = mk_array(deep)
assert(ref_storage_contract(mk_tuple([plain, deep])))
scalar = T_INT
loop i in [0..31): scalar = mk_array(scalar)
assert(not ref_storage_contract(scalar))
assert(ref_storage_contract(mk_array(scalar)))
# A cycle at the cap is still a cycle, rather than a depth overflow.
first = types.len()
loop i in [0..32):
    types.push(TypeInfo(kind = .array, elem = i32(first + (i + 1) % 32)))
assert(not ref_storage_contract(first))
# Queries must observe fields published after an earlier query.
si = structs.len()
structs.push(StructInfo(resolved = true, fields = i32(fields.len()), nfields = 1))
fields.push(Field(type = i32(T_INT)))
record = mk_type(TypeInfo(kind = .struct_, st = i32(si)), [])
assert(not ref_storage_contract(record))
fields[int(structs[si].fields)].type = i32(positive)
assert(ref_storage_contract(record))
assert(not ref_storage_contract(plain))
print("ok")
''')
    binary = tmp_path / 'storage_walk'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'
