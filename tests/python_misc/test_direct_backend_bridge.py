"""The HIR bridge and ordinary µDewy route retain independent execution checks."""
import subprocess

import pytest

from dewy.backend.udewy import direct, emit, lower
from dewy.reporting import SrcFile
from dewy.semantic import check
from udewy.backend import get_backend
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


SOURCES = [
    '''
main=():>int64=>{
    let values:array<int64>=[1 2 3]
    let saved=values
    values[0]=7
    let table:dict<string int64>=['answer'->42]
    let old=table
    table['answer']=7
    let total:int64=0
    loop i in 0..3 {if i=?1 continue\nif i=?3 break\ntotal+=i}
    if total=?2 and saved[0]=?1 and old.get('answer' default=0)=?42 return 42
    return 0
}
''',
    '''
touch=(@state:array<int64 length=1>):>bool=>{state[0]=1 return true}
main=():>int64=>{
    let state:array<int64 length=1>=[0]
    let skipped=false and touch(@state)
    if skipped or state[0] not=?0 return 1
    if false and touch(@state) return 2
    if state[0] not=?0 return 3
    if true or touch(@state) {if state[0] not=?0 return 4}
    let taken=true and touch(@state)
    if not taken or state[0] not=?1 return 5
    return 42
}
''',
    '''
Fn:type=(value:int64):>int64
identity=(value:int64):>int64=>value
choose=(@state:array<int64 length=1>):>Fn=>{state[0]=1 return @identity}
argument=(@state:array<int64 length=1>):>int64=>{
    if state[0]=?1 {state[0]=2 return 42}
    return 0
}
main=():>int64=>{
    let state:array<int64 length=1>=[0]
    let answer=choose(@state)(argument(@state))
    if state[0] not=?2 return 1
    return answer
}
''',
    '''
let bytes:array<uint8>=0x"00 ff ab 12"
main=():>int64=>{
    let text='a🌱é'
    let copy=text
    if bytes.length=?4 and bytes[1]=?255 and copy.length=?3 return 42
    return 0
}
''',
    '''
main=():>int64=>{
    let byte:uint8=250
    let signed:int8=120
    let large:uint64=uint64.max
    let negative:int64=-16
    if byte + 10 not=? 4 return 1
    if signed - (-10) not=? -126 return 2
    if large // 2 not=? 9223372036854775807 return 3
    if large % 2 not=? 1 return 4
    if negative >> 2 not=? -4 return 5
    if large >> 63 not=? 1 return 6
    if (6 nand 3) not=? -3 return 7
    return 42
}
''',
    '''
main=():>int64=>{
    const size:int64=8
    const scratch:int64=__static_alloca__(size)
    const words:int64=__static_words__(40 2)
    __store_i64__(__load_i64__(words) + __load_i64__(words + 8) scratch)
    return __load_i64__(scratch)
}
''',
    '''
let visited:int64=0
visit=(value:bool):>bool=>{visited+=1 return value}
main=():>int64=>{
    if not (false and visit(true)) {
        if visited not=? 0 return 1
    }
    if (true or visit(false)) and (false or visit(true)) {
        if visited not=? 1 return 2
    } else return 3
    loop visited <? 3 and visit(true) {}
    if visited not=? 3 return 4
    return 42
}
''',
    '''
main=():>int64=>{
    let a:uint16=65535
    let b:int16=32767
    let c:uint32=4294967295
    let d:int32=2147483647
    if a + 1 not=? 0 or c + 1 not=? 0 return 1
    if b + 1 not=? -32768 or d + 1 not=? -2147483648 return 2
    if not a not=? 0 or not c not=? 0 return 3
    if not b not=? -32768 or not d not=? -2147483648 return 4
    if (-b) not=? -32767 or (-d) not=? -2147483647 return 5
    return 42
}
''',
]


@pytest.mark.parametrize('source', SOURCES, ids=(
    'aggregates', 'conditions', 'indirect-order', 'unicode-data', 'word-widths', 'static-data',
    'nested-conditions', 'narrow-integer-words'))
def test_bridge_matches_source_route_and_expected_result(tmp_path, source):
    for target in ('x86_64', 'c'):
        file = SrcFile(None, source)
        root = check.typecheck_and_resolve(file, include_prelude=True, target=target,
                                         debug_variables=False)
        program = lower.lower_for_udewy(root, file)
        reference = tmp_path / f'reference-{target}.udewy'
        reference.write_text(emit._emit_program(program, root, debug_locations=False))
        assert entry_point(reference, [], EntryPointOptions(compile_only=True, target=target,
                                                            debug_info=False)) == 0
        expected = subprocess.run([cache_artifact(reference).resolve()], capture_output=True,
                                  timeout=15, check=False)
        assert expected.returncode == 42, expected.stdout + expected.stderr
        backend = get_backend(target)
        backend.debug_info = False
        assembly = direct.compile_program(program, root, backend)
        executable = backend.compile_and_link(assembly, f'direct-{target}', tmp_path)
        actual = subprocess.run([executable.resolve()], capture_output=True, timeout=15, check=False)
        assert (actual.returncode, actual.stdout, actual.stderr) == (
            expected.returncode, expected.stdout, expected.stderr)


def test_cli_bridge_preserves_included_bytes_and_arguments(tmp_path):
    import sys

    payload = tmp_path / 'data.bin'
    payload.write_bytes(b'\x00\xff\x2a')
    source = tmp_path / 'main.dewy'
    source.write_text('''
let bytes=$include_bytes(p"data.bin")
main=(args:array<string>):>int64=>{
    if args.length not=? 2 return 1
    if args[1] not=? 'argument' return 2
    if bytes.length not=? 3 or bytes[1] not=? 255 return 3
    return bytes[2] as int64
}
''')
    for target in ('x86_64', 'c'):
        # Separate input names keep the existing CLI cache independent of target.
        target_source = tmp_path / f'{target}.dewy'
        target_source.write_text(source.read_text())
        result = subprocess.run([sys.executable, '-m', 'dewy', '--target', target,
                                 str(target_source), 'argument'], capture_output=True,
                                timeout=30, check=False)
        assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_static_globals_match_source_data_relocations_and_fallback(target):
    from dewy.semantic import hir, ty
    from dewy.reporting import Span
    from udewy import p0

    loc = Span(0, 0)
    def integer(n):
        return hir.Integer(loc, 'int64', '0d', n)
    def identifier(name, type_='int64'):
        return hir.ExpressedIdentifier(loc, type_, name)
    def call(name, *args):
        return hir.FunctionCall(loc, 'int64', identifier(name), list(args), {})
    def constant(name, expr):
        return hir.Declare(loc, 'void', 'const', name, 'int64', expr)

    signature = ty.FunctionType([], [], None, 'int64')
    literal = hir.FunctionLiteral(loc, signature, [], [], None, 'int64', integer(42))
    globals_ = [
        constant('size', integer(16)),
        constant('text', hir.String(loc, 'int64', 'é🌱')),
        constant('bytes', hir.BasedString(loc, 'int64', '0x', '00ff', b'\x00\xff')),
        constant('scratch', call('__static_alloca__', identifier('size'))),
        constant('callback', identifier('later', signature)),
        constant('words', call('__static_words__', integer(-1), identifier('text'),
                               identifier('bytes'), identifier('scratch'), identifier('callback'))),
        hir.Declare(loc, 'void', 'let', 'mutable', 'int64', integer(7)),
        constant('snapshot', identifier('mutable')),
    ]
    program = lower.LoweredProgram([lower.LoweredFunction('later', literal)], globals_, [],
                                    None, '__startup', False)
    root = hir.Block(loc, 'void', [], True)
    outputs = []
    for use_source in (False, True):
        backend = get_backend(target)
        backend.debug_info = False
        driver = direct._DirectEmitter(program, root, backend)
        fragments = []
        original = driver.fragment
        def fragment(text, parser):
            fragments.append(text)
            return original(text, parser)
        driver.fragment = fragment
        if use_source:
            driver.global_declaration = lambda decl: driver.fragment(
                emit.emit_declare(decl, driver.ctx), p0.parse_program)
        outputs.append(driver.compile())
        if not use_source:
            # An unresolved function and a mutable global retain source
            # handling; inspecting those values must not emit partial data.
            assert len(fragments) == 2
            assert fragments[0].startswith('const callback:')
            assert fragments[1].startswith('const snapshot:')
    assert outputs[0] == outputs[1]
