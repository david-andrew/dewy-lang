"""Omitted record fields use declaration scope and this construction's siblings."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_imported_defaults_keep_namespaces_and_sibling_values(tmp_path):
    (tmp_path / 'helpers.dewy').write_text('''
const seed:int64 = 9
Payload:type = [n:int64 = seed]
''')
    (tmp_path / 'records.dewy').write_text('''
import p"helpers.dewy" as hidden
Record:type = [
    base:int64 = hidden.seed
    payload:hidden.Payload = hidden.Payload[]
    result:int64 = base + hidden.seed
]
''')
    (tmp_path / 'other.dewy').write_text('const seed:int64 = 99')
    source = tmp_path / 'main.dewy'
    source.write_text('''
import p"records.dewy" as records
import p"other.dewy" as hidden
let main = ():>int64 => {
    let base:int64 = 100
    let first = records.Record[]
    let second = records.Record[3]
    let explicit = records.Record[base=4 result=hidden.seed]
    printl(first.base)
    printl(first.payload.n)
    printl(first.result)
    printl(second.result)
    printl(explicit.result)
    return 0
}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['9', '9', '18', '12', '99']
