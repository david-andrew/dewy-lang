"""Native source expressions enter HIR through the shared lexical/type arenas."""

import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.hir_display import type_to_dewy
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    '1', "'hello'", 'true', 'none', '1 + 2', '3 >? 2',
    'let x:int64 = 1\nx + 2', 'const x = 1\nx', '[1 2]',
    'let x:int64 = 1\nx = 2\nx', 'let xs:array<int64> = []\nxs',
    'Count:type = int64\nlet n:Count = 7\nn',
    'let f=(x:int64):>int64 => x + 1\nf(7)',
    'let f=(x:int64):>int64 => { return x }\nf(8)',
    'let first=():>int64 => later()\nlet later=():>int64 => 9\nfirst()',
    'let f=(x:int64|string):>int64 => if x is? int64 x else 0\nf(7)',
    'let f=(x:bool):>int64 => { if x return 1 return 2 }\nf(false)',
    'if true 1 else 2',

]


def test_native_source_values(tmp_path):
    expected = []
    for text in CASES:
        module, _ = check._typecheck_module(SrcFile(None, text))
        expected.append(type_to_dewy(module.type))
    cases = ' '.join(json.dumps(text).replace('{', r'\{') for text in CASES)
    source = tmp_path / 'check.dewy'
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/check.dewy'}" as checking
import p"{ROOT / 'dewy/bootstrap/semantic/type_display.dewy'}" as display
main = ():>int64 => {{
    let cases:array<string> = [{cases}]
    loop text in cases {{
        let source = SrcFile['fixture' text]
        let parsed = parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session = contexts.Session[]
        let lexical = contexts.begin(source parsed.nodes @session)
        let environment = checking.begin(lexical @session)
        let module = checking.block(parsed.root environment @session)
        if module is? Error {{ module.fail return 1 }}
        let node = checking.node_at(module session)
        printl(display.type_to_dewy(node.value_type session.types))
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=90, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == expected
