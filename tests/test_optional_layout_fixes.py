"""Optional payload selection and declared contracts survive nesting and narrowing."""
import shutil
import subprocess

import pytest

from tests.support import Scripts, compiler  # noqa: F401


NARROW_REJECT = {
    'reject_optional_narrow_assign': """main=()=>{let x:int<(>=? 0)>?=2 if x isnt? none {x=-1} printl(x)}""",
    'reject_optional_narrow_compound': """main=()=>{let x:int<(>=? 0)>?=2 if x isnt? none {x-=3} printl(x)}""",
    'reject_optional_field_compound': """R:type=[x:int<(>=? 0)>?]
main=()=>{let r=R[2] if r.x isnt? none {r.x-=3} printl(r.x)}""",
    'reject_narrowed_match_assign': """main=()=>{let x:int<(>=? 0)>?=2 match x {v:int<(>=? 0)>=>{x=-1} <none>=>{}} printl(x)}""",
    'reject_narrowed_call': """weaken=(@x:int)=>{x=-1}
main=()=>{let x:int<(>=? 0)>?=2 if x isnt? none {weaken(@x)} printl(x)}""",
    'reject_narrowed_i8': """main=()=>{let x:int8<(>=? 0)>?=2 if x isnt? none {x=-1} printl(x)}""",
    'reject_narrowed_u64': """main=()=>{let x:uint64<(<=? 100)>?=2 if x isnt? none {x=101} printl(x)}""",
    'reject_narrowed_length_push': """main=()=>{let xs:array<int length <? 3>?=[1 2] if xs isnt? none {xs.push(3)} printl(xs)}""",
    'invalid_optional_length': """main=()=>{
 let xs:array<int length >? 0>?=[1]
 if xs isnt? none {xs.clear()}
 printl(xs)
}""",
    'invalid_optional_string': """main=()=>{
 let s:string<length >? 0>?="hi"
 if s isnt? none {s=""}
 printl(s)
}""",
    'reject_nonnarrowed_replace': """main=()=>{let x:int<(>=? 0)>?=2 x=-1 printl(x)}""",
    'reject_nonnarrowed_scalar': """main=()=>{let x:int<(>=? 0)>=2 x-=3 printl(x)}""",
}

NARROW_VALID = {
    'equivalent_mutable_contract': ('''$runtime_checks
bump=(@x:int<(>=? 0)>)=>{x+=1}
main=()=>{
 let x:int<(>=? 0)>?=2
 if x isnt? none {bump(@x)}
 printl(x)
}''', '3\n'),
    'length_and_string_mutation': ('''$runtime_checks
main=()=>{
 let xs:array<int length >? 0>?=[1]
 if xs isnt? none {xs.push(2)}
 printl(xs)
 let s:string<length >? 0>?="hi"
 if s isnt? none {s="ok"}
 printl(s)
}''', '[1 2]\nok\n'),
    'narrowed_optional_mutation': ("""$runtime_checks
T:type=int<(>=? 0)>
main=()=>{
 let xs:array<T?>=[2 none]
 let p=@xs[0]
 if p isnt? none { p += 3 }
 printl(xs[0] ?? 0)
 let d:dict<string T?>=["x"->2]
 let q=@d["x"]
 if q isnt? none { q += 3 }
 printl(d["x"] ?? 0)
}""", '5\n5\n'),
    'compound_optional_refmath': ("""$runtime_checks
T:type=int<(>=? -10)>
R:type=[v:T?]
main=()=>{
 let x:T?=-7
 if x isnt? none {x += 1 printl(x)}
 let r=R[-7]
 let old=r
 if r.v isnt? none {r.v += 1 printl(r.v)}
 let xs:array<T?>=[-7]
 let d:dict<string T?>=["x"->-7]
 printl(old.v ?? -7)
}""", '-6\n-6\n-7\n'),
    'compound_optional_refi8': ("""$runtime_checks
T:type=int8<(>=? -128)>
R:type=[v:T?]
main=()=>{
 let x:T?=-128
 if x isnt? none {x += 1 printl(x)}
 let r=R[-128]
 let old=r
 if r.v isnt? none {r.v += 1 printl(r.v)}
 let xs:array<T?>=[-128]
 let d:dict<string T?>=["x"->-128]
 printl(old.v ?? -128)
}""", '-127\n-127\n-128\n'),
    'compound_optional_refu64': ("""$runtime_checks
T:type=uint64<(>=? 0)>
R:type=[v:T?]
main=()=>{
 let x:T?=18446744073709551615
 if x isnt? none {x -= 1 printl(x)}
 let r=R[18446744073709551615]
 let old=r
 if r.v isnt? none {r.v -= 1 printl(r.v)}
 let xs:array<T?>=[18446744073709551615]
 let d:dict<string T?>=["x"->18446744073709551615]
 printl(old.v ?? 18446744073709551615)
}""", '18446744073709551614\n18446744073709551614\n18446744073709551615\n'),
}


def check_program(compiler, tmp_path, source, expected, mode):
    path = tmp_path / 'optional.dewy'
    path.write_text(source + '\n')
    binary = tmp_path / 'optional'
    flags = ['--release'] if mode.endswith('release') else []
    if mode.startswith('wasm'):
        flags += ['--target', 'wasm32']
    built = subprocess.run([compiler, 'build', path, '-o', binary, *flags],
                           capture_output=True, text=True, timeout=30)
    if expected is None:
        assert built.returncode != 0, 'invalid stored refinement was accepted'
        assert 'error:' in built.stderr, built.stderr
        return
    assert built.returncode == 0, built.stderr
    command = [binary]
    if mode.startswith('wasm'):
        node = shutil.which('node')
        if node is None:
            pytest.skip('Node is needed to execute wasm')
        scripts = Scripts()
        scripts.feed(binary.with_suffix('.html').read_text())
        runner = tmp_path / 'optional.cjs'
        runner.write_text('\n'.join(scripts.parts))
        command = [node, runner]
    ran = subprocess.run(command, capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected


MODES = ['native', 'native-release', 'wasm', 'wasm-release']


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('name', NARROW_REJECT)
def test_optional_narrowed_reject(compiler, tmp_path, name, mode):
    check_program(compiler, tmp_path, NARROW_REJECT[name], None, mode)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('name', NARROW_VALID)
def test_optional_narrowed_valid(compiler, tmp_path, name, mode):
    check_program(compiler, tmp_path, *NARROW_VALID[name], mode)
