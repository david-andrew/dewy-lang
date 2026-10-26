"""Per-member typing, proofs and runtime behavior survive checked and lowered replay."""
import os
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401
from tools.compiler.member_replay_diff import MODES, compare


SOURCES = {
    'later_debug_name': '''
$runtime_checks
U:type='aa'|'bbb'
make=(text:string):>dict<string U>=>{
    let table:dict<string U>=[]
    loop s in members(U) {table[s]=s}
    let converted:U=text
    table["converted"]=converted
    return table
}
printl(make("aa"))
''',
    'narrowed_path': '''
$runtime_checks
Box:type=[value:array<string>|none]
make=(box:Box)=>{
    let table:dict<string string>=[]
    if box.value isnt? none {
        loop s in members('aa'|'bbb') {table[s]=box.value[0]}
    }
    return table
}
printl(make(Box[value=["x"]]))
''',
    'inferred_text': '''
$runtime_checks
make=()=>{
    let prefix="aa"
    let table:dict<string 'aa'|'bbb'>=[]
    loop s in members('aa'|'bbb') {table[s]=prefix}
    return table
}
printl(make())
''',
    'tables': '''
U:type='aa'|'bbb'
make=():>dict<string U>=>{
    let table:dict<string U>=[]
    loop s in members(U) {table[s]=s}
    return table
}
printl(make())
''',
    'punctuation_like': '''
make=()=>{
    let table:dict<uint8 array<string>>=[]
    loop s in members('aa'|'ab'|'!!'|'???') {
        let raw=bytes(s)
        $runtime_assert raw.length >? 0
        let first=raw[0]
        let letter=b'a' <=? first <=? b'z'
        if not letter {
            if first in? table table[first].push(s) else table[first]=[s]
        }
    }
    return table
}
printl(make())
''',
    'open_proofs': '''
loop s in members('aa'|'bbb') {
    let raw=bytes(s)
    $assert raw.length >? 1
    let first=raw[0]
    $assert first >=? 0
}
''',
    'later_proof_fails': '''
loop s in members('aa'|'bbb') {
    let raw=bytes(s)
    $assert raw.length <? 3
}
''',
    'singleton_proof': "loop s in members('aa'|'bbb') {$assert bytes(s).length >? 1}",
    'singleton_overloads': '''
pick=((s:'aa'):>int64=>1)&((s:'bbb'):>int64=>2)&((s:string):>int64=>3)
loop s in members('aa'|'bbb') {printl(pick(s))}
''',
    'later_conversion_fails': '''
U:type='aa'|'bbb'
make=()=>{
    let table:dict<string 'aa'>=[]
    loop s in members(U) {table[s]=s}
    return table
}
printl(make())
''',
    'constant_diagnostic_order': '''
loop s in members('a'|'bb') {$runtime_assert s =? "a"}
printl(unknown)
''',
    'literal_transform': '''
make=()=>{
    let table:dict<string string>=[]
    loop s in members('aa'|'bbb') {table["{s}!"]=s}
    return table
}
printl(make())
''',
    'narrow_and_jump': '''
loop s in members('aa'|'bbb') {
    if s =? 'aa' {continue}
    printl(s)
}
''',
    'unicode': '''
loop s in members('é'|'hello'|'💧') {
    let raw=bytes(s)
    $runtime_assert raw.length >? 0
    let first=raw[0]
    $assert first >=? 0
}
''',
}
SOURCES.update({
    'panic_later': '''
make=(limit:int64)=>{
    let result:array<string>=[]
    loop s in members('aa'|'bbb'|'c') {
        result.push(s)
        let raw=bytes(s)
        $runtime_assert raw.length <? limit
    }
    return result
}
printl("before")
printl(make(3))
''',
    'bounds_later': '''
$runtime_checks
make=(index:int64)=>{
    let table:dict<string uint8>=[]
    loop s in members('aa'|'b') {
        let raw=bytes(s)
        table[s]=raw[index]
    }
    return table
}
printl("before")
printl(make(1))
''',
    'different_facts': '''
$runtime_checks
make=()=>{
    let table:dict<string uint8>=[]
    loop s in members('aa'|'b') {
        let raw=bytes(s)
        table[s]=raw[1]
    }
    return table
}
printl(make())
''',
    'cleanup_and_alias': '''
$runtime_checks
make=(choose:bool)=>{
    let result:array<array<string>>=[]
    let table:dict<uint8 array<string>>=[]
    loop s in members('a'|'bbb'|'é'|'💧') {
        let raw=bytes(s)
        let first=raw[0]
        if choose and first >? 0 {
            table[first]=[s s]
            result.push(table[first])
            table[first].push(s)
        } else table[first]=[s]
    }
    printl(table)
    return result
}
printl(make(true))
printl(make(false))
''',
    'nested_invocation': '''
$runtime_checks
make=()=>{
    let all:array<string>=[]
    loop i in [0..3) {
        loop s in members('x'|'yz') {all.push(s)}
    }
    loop s in members('é'|'!') {all.push(s)}
    return all
}
printl(make())
printl(make())
''',
    'empty_member': '''
make=()=>{
    let table:dict<string ''|'é'|'💧'>=[]
    loop s in members(''|'é'|'💧') {table[s]=s}
    return table
}
printl(make())
''',
    'different_domains': '''
make=()=>{
    let first:dict<string 'a'|'b'>=[]
    let second:dict<string '0'|'b'|'a'>=[]
    loop s in members('a'|'b') {
        first[s]=s
        second[s]=s
    }
    printl(first)
    return second
}
printl(make())
''',
    'literal_word_collision': '''
make=()=>{
    let table:dict<string 'a'|'b'|'c'>=[]
    let words:array<int64>=[0 1 2]
    loop s in members('a'|'b'|'c') {
        table[s]=s
        words[0]=1
        words[1]=0
        words[2]=2
    }
    printl(words)
    return table
}
printl(make())
''',
})
PANICS = {'panic_later': b'assert', 'bounds_later': b'index', 'different_facts': b'index'}
REJECTED = {'later_proof_fails', 'singleton_overloads', 'later_conversion_fails',
            'constant_diagnostic_order'}


@pytest.mark.parametrize('name', SOURCES)
@pytest.mark.parametrize('mode', MODES)
def test_member_replay_matches_reference(compiler, tmp_path, name, mode):
    source = tmp_path / f'{name}.dewy'
    source.write_text(SOURCES[name])
    same, accepted = compare(compiler, source, mode, tmp_path / 'comparison',
                             execute=True, panic=PANICS.get(name))
    assert same, f'{name}: diagnostics, runtime output, or fallback files differ; see {tmp_path}'
    assert accepted == (name not in REJECTED)


def test_member_replay_is_exercised(compiler, tmp_path):
    source = tmp_path / 'members.dewy'
    source.write_text(SOURCES['tables'] + SOURCES['open_proofs'] + SOURCES['punctuation_like'].replace('make', 'punctuation'))
    run = subprocess.run([compiler, 'build', source, '--target', 'x86_64-linux',
                          '-o', tmp_path / 'program'],
                         env=os.environ | {'DEWY_MEMBERS': 'trace', 'DEWY_EMIT_WORKERS': '1'},
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert sum(': true,' in line for line in run.stderr.splitlines()
               if line.startswith('member template ')) == 3, run.stderr

    assert sum(': true,' in line for line in run.stderr.splitlines()
               if line.startswith('member lowering ')) == 3, run.stderr


@pytest.mark.core_quick
def test_member_lowering_rejects_nonliteral_ir_differences(compiler, tmp_path):
    source = tmp_path / 'lowering.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / (name + '.jo')}'\n"
                              for name in ('member_lowering', 'member_replay', 'lower', 'ir', 'util'))
                      + f"use '{ROOT / 'compiler/ir_types.dewy'}'\n" + '''
part = (scope: int, word: int) -> MemberLowered:
    p = MemberLowered(start = ir.code.len(), regs = ir.vtypes.len(), slots = ir.slot_size.len(), zeros = lower_zeros.len(), scope = scope)
    literal = k_vreg_new(word)
    p.literals.push(MemberLiteral(literal, 7, 0, word))
    slot = new_slot(16, 8)
    address = e_slot(slot)
    e_call(17, [literal, 0, address, e_iconst(0)], -1)
    e_if(0)
    e_store(address, 8, literal, 8)
    e_end()
    start = ir.args.len()
    ir.args.push(i32(slot * 2))
    lower_zeros.push(LowerZero((p.start << 32) | 1, start, 1))
    p.end = ir.code.len()
    p.reg_end = ir.vtypes.len()
    p.slot_end = ir.slot_size.len()
    p.zero_end = lower_zeros.len()
    member_scope_locals[scope] = []
    p
same = (a: MemberLowered, b: MemberLowered) -> bool:
    m = MemberMatch(first = a, next = b, regs = fill(-1, ir.vtypes.len()), reverse = fill(-1, ir.vtypes.len()), slots = fill(-1, ir.slot_size.len()), slot_reverse = fill(-1, ir.slot_size.len()), literal = fill(-1, ir.vtypes.len()), next_literal = fill(-1, ir.vtypes.len()))
    member_match_body(m)
ir_begin("test", 0)
vreg(VI)
vreg(VI)
a = part(1, 0)
b = part(2, 1)
assert(same(a, b), "literal values and private storage may differ")
call = b.start + 1
saved = ir.code[call]
ir.code[call].imm = 18
assert(not same(a, b), "different panic/helper targets")
ir.code[call] = saved
arg = int(saved.a) + 1
ir.args[arg] = 1
assert(not same(a, b), "external values retain identity")
ir.args[arg] = 0
arg = int(saved.a) + 3
ir.args[arg] = i32(k_vreg_new(1))
assert(not same(a, b), "unmarked constants retain their values")
ir.args[arg] = i32(e_iconst(0))
ir_positions.push(1)
ir.code[call].pos = 1
assert(not same(a, b), "panic source positions retain identity")
ir.code[call] = saved
lower_zeros[b.zeros].mark += 1 << 32
assert(not same(a, b), "cleanup must initialize at the same boundary")
lower_zeros[b.zeros].mark -= 1 << 32
assert(same(a, b))
ir.code[a.start + 1] = Ins(.br, 0, 0, 0, 0, 0, 0)
ir.code[call] = ir.code[a.start + 1]
assert(not same(a, b), "branches may not escape a member")
print("ok")
''')
    binary = tmp_path / 'lowering'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout == 'ok\n'


def test_member_lowering_fused_workers(compiler, tmp_path):
    import platform
    import sys
    if not sys.platform.startswith('linux') or platform.machine().lower() not in ('x86_64', 'amd64'):
        pytest.skip('fused workers are x86-64 Linux only')
    from tests.test_core_fused_determinism import check
    source = ROOT / 'tests/ladder/99_dewy_frontend/design.dewy'
    check(compiler, source, tmp_path, DEWY_EMIT_FORCE='1')
    ran = subprocess.run([tmp_path / 'w4'], capture_output=True, timeout=30)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == source.with_name('expected.out').read_bytes()
