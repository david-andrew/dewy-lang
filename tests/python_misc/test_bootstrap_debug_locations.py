"""Native source maps retain grapheme columns and all recognized line ends."""
import json
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.unicode.graphemes import graphemes
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_debug_source_map(tmp_path):
    text = 'first\r\nsecond\n😀x\rthird\u2028last'
    original = SrcFile(tmp_path / 'input.dewy', text)
    source = tmp_path / 'source-map.dewy'
    source.write_text(f'''
from reporting import Span, SrcFile
import p"{ROOT / 'dewy/bootstrap/backend/udewy/debug.dewy'}" as debug
let main=():>int64=>{{
    let source=SrcFile[{json.dumps(str(original.path))} {json.dumps(text, ensure_ascii=False)}]
    let indexed=debug.prepare(source)
    loop index in 0.. and index <? source.body.length {{
        let marker=debug.marker(Span[index index+1] indexed)
        $runtime_assert marker isnt? none
        printl(marker)
    }}
    $runtime_assert debug.marker(Span[0 0] indexed) is? none
    $runtime_assert debug.marker(Span[0 source.body.length+1] indexed) is? none
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                         text=True, timeout=20, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    expected = []
    row, column = 1, 1
    for grapheme in graphemes(text):
        expected.append(f'# @loc {original.path}:{row}:{column}')
        if grapheme in ('\n', '\r\n'):
            row, column = row + 1, 1
        else:
            column += 1
    assert run.stdout.splitlines() == expected
