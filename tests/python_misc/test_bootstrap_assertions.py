"""Assertion checking retains obligations and narrows the reachable continuation.

Reporting lowering is a later native stage. This compares the checked source
contract with the hosted checker, and verifies its deferred failure branches
without claiming they have executed as generated code.
"""

import json
import subprocess
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import ReportException, SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.analyze.effects import _iter_children
from dewy.semantic.hir_display import type_to_dewy
from dewy.semantic.modules import ModuleCompiler
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
# Source, deferred failure branches, collected warnings.
CASES = [
    ('let f=(x:int64):>void=>{$assert (x\r\n >=? 0)}', 0, 0),
    ('let f=()=>{$fail}\nf()', 1, 0),
    ('$assert true', 0, 0),
    ('$assert true, "checked"', 0, 0),
    ('$runtime_assert true, 7', 0, 0),  # dead messages are still checked as expressions
    ('let f=(x:bool):>void=>{$assert x, "must hold"}', 0, 0),
    ('let f=(x:bool):>void=>{$runtime_assert x}', 1, 0),
    ('let f=(x:bool):>void=>{$runtime_assert x, "must hold"}', 1, 0),
    ('let f=(x:int64|string):>int64=>{$runtime_assert x is? int64 return x}\nf(1)', 1, 0),
    ('let f=(x:int64|string):>int64=>{$runtime_assert x is? int64, x return x}\nf(1)', 1, 0),
    ('let f=(x:int64?):>int64=>{$runtime_assert x isnt? none return x}\nf(1)', 1, 0),
    ('let f=(d:dict<string int64> k:string):>int64=>{$runtime_assert k in? d return d[k]}', 1, 0),
    ('let f=(d:dict<string int64> k:string):>int64=>{$runtime_assert k in? d and d.length >? 0 return d[k]}', 1, 0),
    ('let f=(x:int64):>void=>{$assert (x  >=?  0), "positive"}', 0, 0),
    ('let f=():>void=>{$expect true}', 0, 0),
    ('let f=():>void=>{$expect false}', 1, 0),
    ('let f=():>void=>{$expect "a" =? "b"}', 1, 1),
    ('let f=(x:bool):>void=>{$expect x}', 1, 0),
    ('let f=(x:int64|string):>void=>{$expect x is? int64 let y:int64=x}', 1, 0),
    ('let f=():>void=>{$fail}', 1, 0),
    ('let f=():>void=>{$fail "deliberate"}', 1, 0),
]
ERRORS = [
    '$assert false',
    '$runtime_assert false',
    '$assert true, 5',
    '$runtime_assert 5',
    '$runtime_assert true, missing',
    '$expect true',
    '$fail',
    'let f=():>int64=>{$expect true return 1}',
    'let f=():>int64=>{$fail}',
    'let f=(x:bool):>void=>{$runtime_assert x, 7}',
    'let f=():>void=>{$fail 7}',
    'let f=(x:int64|string):>int64=>{$assert x is? int64 return x}',
    'let f=(x:int64|string):>int64=>{$runtime_assert x is? int64, x+1 return x}',
    'let f=(d:dict<string int64> k:string):>int64=>{$runtime_assert k in? d d.clear return d[k]}',
]


def obligations(node):
    result = []
    if isinstance(node, hir.Assert):
        result.append(f'{node.source}:{str(node.runtime).lower()}:{str(node.expect).lower()};')
    if isinstance(node, hir.DictLookup):
        result.append(f'lookup:{str(node.proven).lower()}:{str(node.position is not None).lower()};')
    for child in _iter_children(node):
        result.extend(obligations(child))
    return result


def hosted(text):
    ty.reset_program_brands()
    source = SrcFile(None, text)
    compiler = ModuleCompiler(source)
    compiler._ensure_prelude()
    return check._typecheck_module(source, type_system=compiler.type_system,
                                   registry=compiler.registry, module_loader=compiler,
                                   prelude_bindings=compiler.prelude_bindings)[0]


def test_native_assertion_contracts(tmp_path):
    expected = []
    for text, failures, warnings in CASES:
        root = hosted(text)
        expected.append(f'{type_to_dewy(root.type)}|{"".join(obligations(root))}|{failures}|{warnings}')
    for text in ERRORS:
        with pytest.raises(ReportException):
            hosted(text)

    def literal(text):
        return json.dumps(text).replace('{', r'\{')

    source = tmp_path / 'assertions.dewy'
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
import p"{ROOT / 'dewy/bootstrap/semantic/hir.dewy'}" as hir
summary = (id:addr session:contexts.Session @failures:addr):>string => {{
    let node=checking.node_at(id session)
    let parts:array<string>=[]
    if node is? hir.Assert {{ parts.push("{{node.source}}:{{node.runtime}}:{{node.expect}};") }}
    if node is? hir.DictLookup {{ parts.push("lookup:{{node.proven}}:{{node.position isnt? none}};") }}
    if node is? hir.RuntimeFailure {{
        failures += 1
        $runtime_assert display.type_to_dewy(node.value_type session.types) =? 'never'
        $runtime_assert node.source_file <? session.sources.length
        $runtime_assert session.sources[node.source_file].srcfile.body.length >? 0
    }}
    loop child in hir.children(node) {{ parts.push(summary(child session @failures)) }}
    return parts.join
}}
main = ():>int64 => {{
    let cases:array<string>=[{' '.join(literal(text) for text, _, _ in CASES)}]
    loop text in cases {{
        let source=SrcFile['fixture' text]
        let parsed=parser.parse(source)
        if parsed is? Error {{parsed.fail return 1}}
        let session=contexts.Session[]
        let lexical=contexts.begin(source parsed.nodes @session)
        let env=checking.begin(lexical @session)
        let root=checking.module(parsed.root env @session)
        if root is? Error {{root.fail return 1}}
        let failures:addr=0
        let checked=summary(root session @failures)
        printl("{{display.type_to_dewy(checking.node_at(root session).value_type session.types)}}|{{checked}}|{{failures}}|{{session.warnings.length}}")
    }}
    let errors:array<string>=[{' '.join(literal(text) for text in ERRORS)}]
    loop text in errors {{
        let source=SrcFile['fixture' text]
        let parsed=parser.parse(source)
        if parsed is? Error {{parsed.fail return 1}}
        let session=contexts.Session[]
        let lexical=contexts.begin(source parsed.nodes @session)
        let env=checking.begin(lexical @session)
        let root=checking.module(parsed.root env @session)
        $runtime_assert root is? Error
        $runtime_assert root.title not=? 'native checker implementation pending'
        printl('rejected')
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=120, check=False)
    (tmp_path / 'native-output.txt').write_text(result.stdout)
    (tmp_path / 'expected-output.txt').write_text('\n'.join(expected + ['rejected'] * len(ERRORS)) + '\n')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected + ['rejected'] * len(ERRORS)
