"""A field default that is the zero bytes (a machine integer's 0, 0.0, false, an enumeration's
first member, none) is left to the fill that makes the record: building one stores only the
fields that are not zero. -0.0, true, a later member and given values are stored."""
import re
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

DEWY = '''Kind:type='first' | 'second' | 'third'
R:type=[
    k:Kind='first'
    j:Kind='second'
    a:int32=0
    b:int64=7
    c:uint8=0
    f:float64=0.0
    g:float64=-0.0
    h:float64=1.5
    t:bool=false
    u:bool=true
    o:int64|none=none
]
make=(v:int64):>R=>R[b=v]
main=():>void=>{
    let r=make(3)
    printl"{r.k} {r.j} {r.a} {r.b} {r.c} {r.f} {r.g} {r.h} {r.t} {r.u} {r.o}"
}
'''

SLOPPY = '''enum Kind:
    first, second, third

struct R:
    k: Kind = .first
    j: Kind = .second
    a: i32 = 0
    b: int = 7
    f: f64 = 0.0
    h: f64 = 1.5
    t: bool = false
    u: bool = true

make = (v: int) -> R: R(b = v)

main = ():
    r = make(3)
    print("{r.k} {r.j} {r.a} {r.b} {r.f} {r.h} {r.t} {r.u}")
'''

CASES = {
    # (j, b, g, h, u: the fields not zero)
    'main.dewy': (DEWY, 5, 'first second 0 3 0 0.0 -0.0 1.5 false true none'),
    # (j, b, h, u)
    'main.jo': (SLOPPY, 4, 'first second 0 3 0.0 1.5 false true'),
}


@pytest.mark.parametrize('name', sorted(CASES))
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_zero_defaults_are_the_fill(compiler, tmp_path, name, release):  # noqa: F811
    text, stores, expected = CASES[name]
    source = tmp_path / name
    source.write_text(text)
    binary = tmp_path / 'main'
    flags = ['--release'] if release else []
    if not release:
        # (release inlines make: the default build keeps it to read)
        ir = subprocess.run([compiler, 'build', source, '--ir', '-o', binary],
                            capture_output=True, text=True, timeout=60)
        assert ir.returncode == 0, ir.stdout + ir.stderr
        body = re.search(r'^fn f_make_.*?(?=^fn |\Z)', ir.stdout + ir.stderr, re.M | re.S)
        assert body, ir.stdout + ir.stderr
        assert len(re.findall(r'^\s+store ', body[0], re.M)) == stores, body[0]
    built = subprocess.run([compiler, 'build', source, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == expected
