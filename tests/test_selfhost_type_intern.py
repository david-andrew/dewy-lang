"""Interned type IDs, hashes, growth and COW against the frozen type store."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
types: TypeInfo[] = [TypeInfo()]
args: i32[]
table: i32[]
binding = type_intern_bind(&types, &args, &table)
main = ():
    # Every kind/representation discriminant and signed hash field. These also
    # guard the 60-byte TypeInfo ABI's kind and representation word offsets.
    loop tag in [0..30):
        loop rep in [0, 1]:
            loop bits in [-2147483648, -1, 0, 2147483647]:
                t = TypeInfo(kind=TK(tag), rep=RepId(rep), elem=7, st=-1, bits=i32(bits), mutmask=-2147483648, sign=true)
                print(type_intern_hash(&t, [0, -1, 9223372036854775807]))
    t = TypeInfo(kind=.int_, bits=64, sign=true, size=8, align=8)
    assert(type_intern(&t, []) == 1)
    v = TypeInfo(kind=.var, id=1)
    assert(type_intern(&v, []) == 2)
    assert(type_intern(&v, []) == 3)
    param = TypeInfo(kind=.param, id=7, bits=7)
    print(type_intern(&param, []))
    print(type_intern(&param, []))
    # Inference-containing records are fresh; concrete records reuse their IDs.
    loop elem in [1, 2]:
        t = TypeInfo(kind=.array, elem=i32(elem))
        print(type_intern(&t, []))
        print(type_intern(&t, []))
        t = TypeInfo(kind=.tuple)
        print(type_intern(&t, [elem, 1]))
        print(type_intern(&t, [elem, 1]))
    saved_types = types
    saved_args = args
    saved_table = table
    nt = types.len()
    na = args.len()
    t = TypeInfo(kind=.fn_, elem=1, mutmask=5, bits=2, sign=true)
    first = type_intern(&t, [1, 1, 1])
    assert(type_intern(&t, [1, 1, 1]) == first)
    assert(saved_types.len() == nt and saved_args.len() == na and saved_table != table, "arena/table snapshots preserved")
    # Record/union producers can append types without touching the hash table.
    loop k in [0..10000): types.push(TypeInfo(kind=.struct_, st=i32(k + 1)))
    t = TypeInfo(kind=.int_, bits=32)
    print(type_intern(&t, []))
    assert(table.len() >= types.len() * 2, "one rehash accommodates externally appended types")
    loop k in [1, 2, 99, 9999]:
        t = TypeInfo(kind=.struct_, st=i32(k))
        id = type_intern(&t, [])
        assert(types[id].st == i32(k))
        print(id)
    print(type_intern(&param, []))
    print(type_intern(&param, []))
    loop t in types: print("{int(t.kind)}:{t.elem}:{t.args}:{t.nargs}:{t.st}:{t.flags}:{t.bits}:{t.id}:{t.mutmask}:{t.sign}:{int(t.rep)}")
    print(args)
    print(table)
    # Rebinding a second arena never keeps a stale element/table view.
    types = [TypeInfo()]
    args = []
    table = []
    t = TypeInfo(kind=.bool_, size=1, align=1)
    print(type_intern(&t, []))
    print(type_intern(&t, []))
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_intern_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('checker_types', 'type_intern'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'checker_types.{extension}'\nuse 'type_intern.{extension}'\n" + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
