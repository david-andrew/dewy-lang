"""Source type expressions pass through the native parser and type visitor."""

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check, ty
from dewy.semantic.hir_display import type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    'int64', 'addr', 'nat32', 'string?', '-17', '0xFE', '0t1T', '184467440737095516170',
    "'hello'", 'array<int>', 'array<uint length=4>', 'array<array<string>>',
    "dict<'a'|'b' int64>", "totaldict<'a'|'b' int64>", 'set<int>', 'range<int64>',
    '[x:int64 y:string]', '[x:int64 = 2]', 'const [x:int64 y:string]',
    '(x:int64 @out:array<string>):>bool', '((x):>int64)?', 'int64|none',
    'int64<i => i >=? 0>', 'string<length >? 0>', 'array<int64 1 <=? length <=? 8>',
    'int64 & ~0', '~0 & int64', 'int64 & ~(0|1)', 'nat64 & ~0',
    '(0|[value:int64]) & ~0',
    'int64<n => n not=? 0>', 'uint8<radix => radix =? alphabet.length>',
    'const [alphabet:string radix:uint8<radix =? alphabet.length> = alphabet.length]',
    'Box:type = <T>[item:T]\nBox<int64>',
    'Choice:type = <T of int>(T|none)\nChoice<uint8>',
    'Pair:type = <T U of T>[first:T second:U]\nPair<int int64>',
    'Later:type = First\nFirst:type = int64\nLater',
    'Node:type = [value:int64 next:Node|none]\nNode',
    '[x:int64] & [y:string]', '[x:int] & [x:int64]',
    '[f=(x:int64):>int64 => x]', '[x=1 flag=true name="hi"]', '[xs=[1 2]]',
    'Parent:type = type of [x:int64 = 1]\nChild:type = type of Parent & [x=2]\nChild',
    'Token = $abstract type of [loc:int64]\nNumber = type of Token & [value:int64]\nNumber',
    'Missing:type = type of error\nMissing',
    'Message:type = type of error & [text:string]\nMessage',
    'none & <tok is? int64>', 'true & <n >? 0> | false',
    '(tok:int64|string):> tok is? int64', '(@xs:array<int64>):> <xs.length >? 0>',
    '(x:int64):> <(y:string):>int64>', '[sign:-1|1]',
    '[read:(x:int64):>string notify:(@xs:array<int64>):> <xs.length >? 0>]',
]

ERROR_CASES = [
    '[x:int8] & [x:int64]',
    'Twice:type = type of any & type of any\nTwice',
    'Unknown', 'array<int64 length=-1>', 'totaldict<string int64>',
    '[x:int64 x:string]', 'int64<0 <=? length =? 3 >? 1>',
    'none & <int64>', 'true & <n >? 0> | true',
    'Node:type = [next:Node]\nNode', 'A:type = B\nB:type = A\nA',
    'Box:type = <T>[item:T]\nBox',
    'Box:type = <T of int>[item:T]\nBox<string>',
    '(0|[value:int64]) & ~1',
]


def hosted_type(text):
    # This harness enters below the program driver. Each native Session is a
    # fresh program, so reset the hosted driver's compilation-owned brands too.
    ty.reset_program_brands()
    source = SrcFile(None, text)
    root, _ = check._parse_module(source)
    context = check.Context(source)
    if len(root.inner) > 1:
        _, context = check._typecheck_module(source, block=replace(root, inner=root.inner[:-1]))
        context = context.module or context
    return check.ast_to_type(root.inner[-1], ctx=context)


def test_native_source_type_check(tmp_path):
    expected = [type_to_dewy(hosted_type(text)) for text in CASES]
    for text in ERROR_CASES:
        with pytest.raises((check.UserError, check.TypeCheckError, check.NotImplementedYet)):
            hosted_type(text)
    source = tmp_path / 'type_check.dewy'
    inputs = ' '.join(json.dumps(case, ensure_ascii=False).replace('{', r'\{') for case in CASES)
    errors = ' '.join(json.dumps(case, ensure_ascii=False).replace('{', r'\{') for case in ERROR_CASES)
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/parser/t1.dewy'}" as tokens
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/type_check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
main = ():>int64 => {{
    let cases:array<string> = [{inputs}]
    loop text in cases {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let root = tokens.node_at(parsed.nodes parsed.root)
        $runtime_assert root is? parser.Block and root.inner.length >? 0
        let session = contexts.Session[]
        let context = contexts.begin(source parsed.nodes @session)
        loop statement in root.inner {{
            let alias = checking.predeclare_alias(statement context @session)
            if alias is? Error {{ alias.fail return 1 }}
        }}
        let value = checking.resolve(root.inner[root.inner.length - 1] context @session)
        if value is? Error {{ value.fail return 1 }}
        printl(display.type_to_dewy(value session.types))
    }}
    let invalid:array<string> = [{errors}]
    loop text in invalid {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let root = tokens.node_at(parsed.nodes parsed.root)
        $runtime_assert root is? parser.Block and root.inner.length >? 0
        let session = contexts.Session[]
        let context = contexts.begin(source parsed.nodes @session)
        loop statement in root.inner {{
            let alias = checking.predeclare_alias(statement context @session)
            if alias is? Error {{ alias.fail return 1 }}
        }}
        let value = checking.resolve(root.inner[root.inner.length - 1] context @session)
        $runtime_assert value is? Error
        $runtime_assert value.pointers.length >? 0 and value.pointers[0].message.length >? 0
        printl('rejected')
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected + ['rejected'] * len(ERROR_CASES)
