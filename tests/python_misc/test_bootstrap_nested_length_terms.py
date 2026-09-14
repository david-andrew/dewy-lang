"""Native dependent field routes survive contracts and expire after writes."""
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_nested_length_terms import APPEND, PREFIX, index_snapshot_source, positive_source
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_nested_lengths(binary, tmp_path):
    cases = [
        ('contracts', positive_source(), 0), ('append', APPEND, 0),
        ('array-snapshot', index_snapshot_source('array<int64>', '[42]', '[]'), 0),
        ('string-snapshot', index_snapshot_source('string', "'x'", "''"), 0),
    ]
    for i, change in enumerate(['table.inner.entries=[]', 'table.inner=Inner[[]]',
                                'table=Table[Inner[[]] []]']):
        cases.append((f'invalidated-{i}', PREFIX + f'''
main=():>int64=>{{
    let table=Table[Inner[[42]] []]
    let index=last(table)
    {change}
    return table.inner.entries[index]
}}
''', 1))
    cases.extend([
        ('other-root', PREFIX + '''
main=():>int64=>{
    let first=Table[Inner[[42]] []]
    let second=Table[Inner[[]] []]
    return read(second last(first))
}
''', 1),
        ('snapshot-input', PREFIX + '''
main=():>int64=>{
    let table=Table[Inner[[42]] []]
    return read(table {table.inner.entries=[42 1] 1})
}
''', 1),
        ('snapshot-result', PREFIX + '''
first=(table:Table ignored:int64):>addr<i=>i <? table.inner.entries.length>=>{
    $runtime_assert table.inner.entries.length >? 0
    return 0
}
clear=(@table:Table):>int64=>{table.inner.entries=[] return 0}
main=():>int64=>{
    let table=Table[Inner[[42]] []]
    let index=first(table clear(@table))
    return table.inner.entries[index]
}
''', 1),
        ('bad-append', APPEND.replace('    return id\n}', '    return table.entries.length\n}'), 1),
        ('index-before-append', APPEND.replace('    let id=intern(@table 42)\n    return table.entries[id]',
                                             '    return table.entries[intern(@table 42)]'), 1),
    ])
    for name, body, status in cases:
        source = tmp_path / f'{name}.dewy'
        source.write_text(body)
        result = subprocess.run([binary, source], capture_output=True, text=True,
                                timeout=30, check=False)
        assert result.returncode == status, (name, result.stdout, result.stderr)
        if status:
            assert any(message in result.stdout + result.stderr for message in (
                'not proven in bounds', 'cannot prove refinement', 'refinement refuted',
            )), (name, result.stdout, result.stderr)


def test_native_nested_length_contracts(tmp_path):
    output = tmp_path / 'source-validation.udewy'
    output.write_text(codegen(SrcFile.from_path(ROOT / 'tests/fixtures/bootstrap_source_validation.dewy'),
                              debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    check_nested_lengths(cache_artifact(output).resolve(), tmp_path)
