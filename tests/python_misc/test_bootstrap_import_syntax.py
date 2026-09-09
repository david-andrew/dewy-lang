"""Native import forms retain namespace and selected-binding intent."""

import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    'import units',
    'import linux.system as system',
    'from units import Duration',
    'from units import (Duration as Time Length)',
    'import (Duration Length as Distance) from units',
    'import p"relative.dewy" as helper',
]


def test_native_import_syntax(tmp_path):
    cases = ' '.join(json.dumps(text) for text in CASES)
    source = tmp_path / 'imports.dewy'
    source.write_text(f'''from reporting import SrcFile, Error
import p"{ROOT / 'dewy/bootstrap/parser/p0.dewy'}" as parser
import p"{ROOT / 'dewy/bootstrap/parser/t1.dewy'}" as tokens
import p"{ROOT / 'dewy/bootstrap/semantic/context.dewy'}" as contexts
import p"{ROOT / 'dewy/bootstrap/semantic/import_syntax.dewy'}" as imports
main = ():>int64 => {{
    let cases:array<string>=[{cases}]
    loop text in cases {{
        let source=SrcFile['fixture' text]
        let parsed=parser.parse(source)
        if parsed is? Error {{ parsed.fail return 1 }}
        let session=contexts.Session[]
        let context=contexts.begin(source parsed.nodes @session)
        let root=tokens.node_at(parsed.nodes parsed.root)
        $runtime_assert root is? parser.Block and root.inner.length =? 1
        let spec=imports.read(root.inner[0] context session)
        if spec is? Error {{ spec.fail return 1 }}
        $runtime_assert spec isnt? none
        let library=imports.library_name(spec.path parsed.nodes)
        let parts:array<string>=[if library is? none 'path' else library]
        if spec.namespace isnt? none {{ parts.push("namespace:{{spec.namespace}}") }}
        else if spec.names is? none {{ parts.push('all') }}
        else {{ loop name in spec.names {{ parts.push("{{name.source}}:{{name.local}}") }} }}
        printl(parts.join('|'))
    }}
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        'units|all', 'linux/system|namespace:system', 'units|Duration:Duration',
        'units|Duration:Time|Length:Length', 'units|Duration:Duration|Length:Distance',
        'path|namespace:helper',
    ]
