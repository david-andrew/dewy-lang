"""Native emission matches hosted operand rules and produces runnable µDewy."""
import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen, emit
from dewy.reporting import Span, SrcFile
from dewy.semantic import hir, ty
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def integer(value, type_='int64', prefix='0d'):
    return hir.Integer(LOC, type_, prefix, value)


def call(name, arguments, result='int64', parameter=None):
    signature = ty.FunctionType([ty.PosOrKwArg(None, parameter or arg.type) for arg in arguments], [], None, result)
    return hir.FunctionCall(LOC, result, hir.ExpressedIdentifier(LOC, signature, name), arguments, {})


def test_native_emitter_words_and_functions(tmp_path):
    add = call('__add__', [integer(20), integer(22)])
    signature = ty.FunctionType([], [], None, 'int64')
    main = hir.FunctionLiteral(LOC, signature, [], [], None, 'int64', add)
    global_value = hir.ExpressedIdentifier(LOC, 'int64', 'score')
    global_declaration = hir.Declare(LOC, 'void', 'let', 'score', 'int64', integer(0))
    startup = hir.Assign(LOC, 'void', global_value, '=', integer(40))
    user_main = hir.FunctionLiteral(LOC, signature, [], [], None, 'int64', call('__add__', [global_value, integer(2)]))
    shadow = hir.Declare(LOC, 'void', 'let', 'direct', signature, hir.ExpressedIdentifier(LOC, signature, 'callback'))
    cases = [
        integer(42), integer(-17), integer(255, prefix='0x'), integer(5, prefix='0b'),
        hir.String(LOC, ty.StringType(), 'quote" slash\\\nStraße 😀'),
        hir.BasedString(LOC, ty.BinaryLiteralType(b'\x00\x80\xff'), '0x', '0080ff', b'\x00\x80\xff'),
        add,
        call('__mul__', [add, integer(3)]),
        call('__add__', [integer(250, 'uint8'), integer(10, 'uint8')], 'uint8'),
        call('__sub__', [integer(120, 'int8'), integer(-10, 'int8')], 'int8'),
        call('__floordiv__', [integer(18446744073709551615, 'uint64'), integer(2, 'uint64')], 'uint64'),
        call('__rshift__', [integer(-16), integer(2, 'uint8')]),
        call('__rshift__', [integer(16, 'uint64'), integer(2, 'uint8')], 'uint64'),
        call('__nand__', [integer(6), integer(3)]),
        call('__unary_sub__', [integer(7)]),
        call('direct', [integer(-7)]),
        call('callback', [integer(7)]),
        hir.ShortCircuit(LOC, 'bool', 'and', hir.Bool(LOC, 'bool', True), hir.Bool(LOC, 'bool', False)),
        hir.Transmute(LOC, 'uint64', integer(7)),
        hir.Block(LOC, 'void', [hir.Return(LOC, 'never', integer(42))], True),
        hir.Break(LOC, 'never'),
        hir.Block(LOC, 'int64', [hir.Block(LOC, 'void', [shadow], False), call('direct', [])], True),
    ]
    root = hir.Block(LOC, 'void', [*cases, main, global_declaration, startup, user_main], True)
    type_lines = []
    build = type_builder(type_lines)
    node_lines, _, names = emit_hir(root, type_value=build, with_names=True)
    source = tmp_path / 'emitter.dewy'
    source.write_text(f'''
from reporting import Span, SrcFile
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/backend/udewy/emit.dewy'}" as emit
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
main = ():>int64 => {{
    let span=Span[0 0]
    let srcfile=SrcFile['input' '']
    let nodes:array<hir.AST>=[]
    let type_nodes:array<types.Type>=[]
{chr(10).join(type_lines)}
{chr(10).join(node_lines)}
    let input=emit.Input[nodes type_nodes]
    let scope=emit.Scope[direct_functions=set['direct' 'main']]
    let state=emit.State[]
    loop id in [{' '.join(names[id(case)] for case in cases)}] {{
        printl(emit.text_literal(emit.ast(id @scope input @state)))
    }}
    let function=hir.node_at(nodes {names[id(main)]})
    $runtime_assert function is? hir.FunctionLiteral
    let code=emit.function_decl('main' function scope input @state)
    if state.problem isnt? none {{state.problem.fail}}
    printl('PROGRAM')
    printl(code)
    printl('STARTUP')
    let executable=program.Program[
        functions=[program.Function['user_main' {names[id(user_main)]}]]
        globals=[{names[id(global_declaration)]}]
        startup_items=[{names[id(startup)]}]
        user_main_symbol='user_main'
        needs_startup=true
    ]
    let startup_code=program.render(executable input)
    if startup_code is? Error {{startup_code.fail}}
    printl(startup_code)
    printl('EMPTY')
    let empty_code=program.render(program.Program[functions=[]] input)
    if empty_code is? Error {{empty_code.fail}}
    printl(empty_code)
    return 0
}}
''')
    seed_output = source.with_suffix('.udewy')
    seed_output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed_output, [], EntryPointOptions(compile_only=True)) == 0
    native = subprocess.run([cache_artifact(seed_output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert native.returncode == 0, native.stderr + native.stdout
    observations, programs = native.stdout.split('PROGRAM\n')
    program, programs = programs.split('STARTUP\n')
    startup_program, empty_program = programs.split('EMPTY\n')
    context = emit.EmitContext({'direct', 'main'}, set(), debug_locations=False)
    expected = [emit.emit_string(hir.String(LOC, ty.StringType(), emit.emit_ast(case, context))) for case in cases]
    assert observations.splitlines() == expected
    assert program.strip() == emit.emit_function_decl('main', main, context)
    for name, text, expected_exit in [('main', program, 42), ('startup', startup_program, 42), ('empty', empty_program, 0)]:
        output = tmp_path / f'native-emitted-{name}.udewy'
        output.write_text(text)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert result.returncode == expected_exit


def test_native_include_paths_use_preprocessor_spelling(tmp_path):
    paths = [tmp_path / name for name in ['plain.bin', 'a"b.bin', 'a\\b.bin', 'a\nb.bin']]
    for path in paths:
        path.write_bytes(b'*')
    source = tmp_path / 'include-emitter.dewy'
    source.write_text(f'''
from reporting import Span, Error
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/backend/udewy/emit.dewy'}" as emit
import p"{ROOT / 'dewy/bootstrap/backend/udewy/program.dewy'}" as program
let main=():>int64=>{{
    loop path in [{' '.join(json.dumps(str(path)) for path in paths)}] {{
        let nodes:array<hir.AST>=[]
        let type_nodes:array<types.Type>=[]
        let span=Span[0 0]
        let word=types.primitive('int64' @type_nodes)
        let byte=types.primitive('uint8' @type_nodes)
        let load_type=types.function_type([types.PosOrKwArg[none word]] [] none byte [] @type_nodes)
        let main_type=types.function_type([] [] none byte [] @type_nodes)
        let data=hir.append_node(@nodes hir.BasedString[span word '0x' '2a' [42] path])
        let load=hir.append_node(@nodes hir.ExpressedIdentifier[span load_type '__load_u8__'])
        let value=hir.append_node(@nodes hir.FunctionCall[span byte load [data] []])
        let result=hir.append_node(@nodes hir.Return[span types.primitive('never' @type_nodes) value])
        let body=hir.append_node(@nodes hir.Block[span byte [result] true])
        let function=hir.append_node(@nodes hir.FunctionLiteral[span main_type [] [] none byte body])
        let text=program.render(program.Program[functions=[program.Function['main' function]]] emit.Input[nodes type_nodes])
        if text is? Error {{text.fail}}
        printl('PROGRAM')
        printl(text)
    }}
    return 0
}}
''')
    seed = source.with_suffix('.udewy')
    seed.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(seed, [], EntryPointOptions(compile_only=True)) == 0
    native = subprocess.run([cache_artifact(seed).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert native.returncode == 0, native.stdout + native.stderr
    programs = native.stdout.split('PROGRAM\n')[1:]
    assert len(programs) == 4
    assert programs[0].startswith(f'$include_bytes(p"{paths[0]}")')
    for index, code in enumerate(programs):
        if index:
            assert '$include_bytes(' not in code and '0x"2a"' in code
        output = tmp_path / f'include-{index}.udewy'
        output.write_text(code)
        assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], timeout=10, check=False)
        assert result.returncode == 42
