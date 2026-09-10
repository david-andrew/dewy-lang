"""Representation propagation agrees with the hosted pass on checked HIR.

The fixture supplies bounds-analysis flags explicitly. This exercises the
representation pass without treating unchecked source as proof of word fit.
"""
import json
import subprocess
from pathlib import Path

from test_bootstrap_effects import emit_hir
from test_bootstrap_initialization import type_builder

from dewy.backend.udewy import codegen
from dewy.reporting import Span, SrcFile
from dewy.semantic import bindings, hir, ty
from dewy.semantic.analyze.representation import _RepresentationPass
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
LOC = Span(0, 0)


def test_native_integer_representations(tmp_path):
    registry = bindings.BindingRegistry()
    nonzero = ty.ObjectType((ty.ObjectField('sign', ty.union(ty.IntegerLiteralType(-1), ty.IntegerLiteralType(1))), ty.ObjectField('limbs', ty.ArrayType('uint64'))))
    big = ty.union(ty.IntegerLiteralType(0), nonzero)
    prelude = {}
    big_binding = registry.allocate(object(), 'BigInt', 'value', LOC)
    big_binding.type_value = big
    prelude['BigInt'] = big_binding
    for name, args, ret in [('_bigint_mul', [big, big], big), ('_bigint_from_int', ['int64'], big)]:
        binding = registry.allocate(object(), name, 'function', LOC)
        binding.type = ty.FunctionType([ty.PosOrKwArg(None, arg) for arg in args], [], None, ret)
        prelude[name] = binding
    declarations = []
    flagged = []

    def number(n, value_type='int'):
        return hir.Integer(LOC, value_type, '0d', n)

    def read(binding):
        return hir.ExpressedIdentifier(LOC, binding.type, binding.name, binding_id=binding.id)

    def declare(name, value):
        binding = registry.allocate(object(), name, 'value', LOC)
        binding.type = 'int'
        node = hir.Declare(LOC, 'void', 'let', name, 'int', value, binding_id=binding.id)
        binding.declaration = node
        declarations.append(node)
        return binding

    def multiply(left, right):
        function = hir.ExpressedIdentifier(LOC, ty.FunctionType([ty.PosOrKwArg(None, 'int'), ty.PosOrKwArg(None, 'int')], [], None, 'int'), '__mul__')
        call = hir.FunctionCall(LOC, 'int', function, [left, right], {})
        flagged.append(call)
        return call

    huge = declare('huge', number(2**100))
    product = declare('product', multiply(number(3), number(4)))
    accumulator = declare('accumulator', number(0))
    declarations.append(hir.Assign(LOC, 'void', read(accumulator), '=', multiply(read(accumulator), number(2))))
    declarations.extend([read(huge), read(product), read(accumulator)])
    root = hir.Block(LOC, 'void', declarations, True)
    type_lines = []
    build = type_builder(type_lines)
    lines, root_id, names = emit_hir(root, type_value=build, with_names=True)
    registry_lines = []
    for binding in registry.by_id.values():
        registry_lines.append(f'''registry.by_id[{binding.id}]=bindings.Binding[id={binding.id} name={json.dumps(binding.name)} kind={json.dumps(binding.kind)} loc=span
value_type={"none" if binding.type is None else build(binding.type)} type_value={"none" if binding.type_value is None else build(binding.type_value)}
declaration={"none" if binding.declaration is None else names[id(binding.declaration)]}]''')
    big_id, nonzero_id = build(big), build(nonzero)
    prelude_text = '[' + ' '.join(f'{json.dumps(name)}->{binding.id}' for name, binding in prelude.items()) + ']'
    flags_text = '[' + ' '.join(f'{names[id(node)]}->representations.Unfit[none "int64"]' for node in flagged) + ']'
    hosted = _RepresentationPass(registry, SrcFile(None, ''), prelude, {id(node): (node, None, 'int64') for node in flagged})
    hosted.run(root)
    expected = [f'{binding.name}:{str(binding.id in hosted.big_bindings).lower()}' for binding in [huge, product, accumulator]]
    source = tmp_path / 'representations.dewy'
    source.write_text(f'''
from reporting import SrcFile, Span, Error
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
import p"{ROOT / 'dewy/bootstrap/semantic/ty.dewy'}" as types
import p"{ROOT / 'dewy/bootstrap/semantic/bindings.dewy'}" as bindings
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/propositions.dewy'}" as facts
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/representation.dewy'}" as representations
import p"{ROOT / 'dewy/bootstrap/semantic/analyze/intervals.dewy'}" as ranges
main=():>int64=>{{
    let span=Span[0 0]
    let srcfile=SrcFile["representation fixture" ""]
    let nodes:array<hir.AST>=[]
    let type_nodes:array<types.Type>=[]
    let registry=bindings.Registry[]
{chr(10).join(type_lines + lines + registry_lines)}
    let session=contexts.Session[hir=nodes types=type_nodes registry=registry]
    let state=representations.State[srcfile {prelude_text} {big_id} {nonzero_id} {flags_text}]
    let result=representations.run({root_id} @state @session)
    if result is? Error {{result.fail}}
    $runtime_assert state.unfit.length =? 0
    loop id in [{huge.id} {product.id} {accumulator.id}] {{
        let binding=bindings.binding_at(session.registry id)
        printl("{{binding.name}}:{{id in? state.big_bindings}}")
        $runtime_assert binding.value_type =? state.big_type and binding.store_type =? state.big_type
    }}
    let product=hir.node_at(session.hir {names[id(product.declaration)]})
    $runtime_assert product is? hir.Declare
    let call=hir.node_at(session.hir product.expr)
    $runtime_assert call is? hir.FunctionCall
    let callee=hir.node_at(session.hir call.func)
    $runtime_assert callee is? hir.ExpressedIdentifier and callee.name =? '_bigint_mul'
    let huge=hir.node_at(session.hir {names[id(huge.declaration)]})
    $runtime_assert huge is? hir.Declare
    let literal=hir.node_at(session.hir huge.expr)
    $runtime_assert literal is? hir.ObjectLiteral and literal.integer_value isnt? none
    $runtime_assert literal.integer_value =? {2**100}
    # A big local cannot silently change a function's declared word ABI.
    let word=types.primitive('int' @session.types)
    let never=types.primitive('never' @session.types)
    let signature=types.function_type([] [] none word [] @session.types)
    let returned=hir.append_node(@session.hir hir.Return[span never huge.expr])
    let function=hir.append_node(@session.hir hir.FunctionLiteral[span signature [] [] none word returned])
    let return_state=representations.State[srcfile {prelude_text} {big_id} {nonzero_id}]
    let return_error=representations.run(function @return_state @session)
    $runtime_assert return_error is? Error and return_error.title =? 'a big integer is returned from a word-sized function'
    let parameter_type=types.function_type([types.PosOrKwArg['value' word]] [] none word [] @session.types)
    let callee=hir.append_node(@session.hir hir.ExpressedIdentifier[span parameter_type 'takes_word' none])
    let call=hir.append_node(@session.hir hir.FunctionCall[span word callee [huge.expr] []])
    let call_state=representations.State[srcfile {prelude_text} {big_id} {nonzero_id}]
    let call_error=representations.run(call @call_state @session)
    $runtime_assert call_error is? Error and call_error.title =? 'a big integer is passed to a word-sized parameter'
    # A refuted narrowing stays an error after integer promotion settles.
    let integer=hir.append_node(@session.hir hir.Integer[span word '0d' 1000])
    let cast=hir.append_node(@session.hir hir.ValueCast[span types.primitive('uint8' @session.types) integer])
    let narrow_state=representations.State[srcfile {prelude_text} {big_id} {nonzero_id} [cast->representations.Unfit[ranges.exact(1000) 'uint8']]]
    let narrow_error=representations.run(cast @narrow_state @session)
    $runtime_assert narrow_error is? Error and narrow_error.title =? 'this integer does not fit `uint8`'
    # Knowing a call's result value does not authorize dropping its effects.
    let forty_two=types.integer_literal(42 @session.types)
    let producer_type=types.function_type([] [] none forty_two [] @session.types)
    let producer=hir.append_node(@session.hir hir.ExpressedIdentifier[span producer_type 'tick' none])
    let effect=hir.append_node(@session.hir hir.FunctionCall[span forty_two producer [] []])
    let preserved=representations.to_big(effect @state @session)
    let block=hir.node_at(session.hir preserved)
    $runtime_assert block is? hir.Block and block.items.length =? 2 and block.items[0] =? effect
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
