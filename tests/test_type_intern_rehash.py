"""A rehash leaves out type and module values: records appended per use, never looked up."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
types: TypeInfo[] = [TypeInfo()]
args: i32[]
table: i32[]
binding = type_intern_bind(&types, &args, &table)
main = ():
    int_type = TypeInfo(kind=.int_, bits=64, sign=true, size=8, align=8)
    first = type_intern(&int_type, [])
    loop k in [0..5000):
        types.push(TypeInfo(kind=.typeval, elem=i32(first)))
        types.push(TypeInfo(kind=.module, mod=i32(k)))
    types.push(TypeInfo(kind=.struct_, st=7))
    appended = types.len() - 1
    # (growing to hold what was appended places every record again)
    bool_type = TypeInfo(kind=.bool_, size=1, align=1)
    second = type_intern(&bool_type, [])
    assert(table.len() >= types.len() * 2)
    held = 0
    loop id in table:
        if id == 0: continue
        held += 1
        assert(types[int(id)].kind != .typeval and types[int(id)].kind != .module)
    assert(held == 3)
    # What the table holds is found as before, appended records included.
    assert(type_intern(&int_type, []) == first and type_intern(&bool_type, []) == second)
    struct_type = TypeInfo(kind=.struct_, st=7)
    assert(type_intern(&struct_type, []) == appended)
    print("ok")
'''


def test_rehash_leaves_out_values(compiler, tmp_path):  # noqa: F811
    for stem in ('checker_types', 'type_intern'):
        (tmp_path / f'{stem}.dewy').write_text((ROOT / f'compiler/{stem}.dewy').read_text())
    source, binary = tmp_path / 'driver.jo', tmp_path / 'driver'
    source.write_text("use 'checker_types.dewy'\nuse 'type_intern.dewy'\n" + DRIVER)
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
    assert ran.stdout == 'ok\n'
