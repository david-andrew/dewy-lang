"""Import aliases obey the same lexical shadowing as values and parameters."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_namespace_shadowing_uses_binding_identity(tmp_path):
    library = tmp_path / 'records.dewy'
    library.write_text('let value:int64 = 9\nlet Item:type = [value:int64]\n')
    source = tmp_path / 'main.dewy'
    source.write_text(f'''
import p"{library}" as records
let parameter = (records:[value:int64]):>int64 => records.value
let local = ():>int64 => {{
    let records = [value=5]
    return records.value
}}
let callable = (records:<(x:int64):>int64>):>int64 => records(3)
let plus = (x:int64):>int64 => x + 1
let imported = (records:int64):>int64 => {{
    import p"{library}" as records
    let item:records.Item = records.Item[records.value]
    return item.value
}}
let main = ():>int64 => {{
    let item = records.Item[7]
    printl(parameter(item))
    printl(local())
    printl(callable(@plus))
    printl(imported(0))
    printl(records.value)
    return 0
}}
''')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['7', '5', '4', '9', '9']


def test_resolved_namespace_call_does_not_probe_indexing(tmp_path, monkeypatch):
    from dewy.semantic import check
    from dewy.parser import p0, t1

    library = tmp_path / 'operations.dewy'
    library.write_text('square=(value:int64):>int64=>value*value\n')
    source = tmp_path / 'caller.dewy'
    source.write_text(f'''
import p"{library}" as operations
let main=():>int64=>operations.square(6)+6
''')
    attempted = []
    original = check._tcr_index

    def index(binop, **kwargs):
        left = binop.left
        if (isinstance(left, p0.BinOp) and isinstance(left.left, p0.Atom)
                and isinstance(left.left.item, t1.Identifier)
                and left.left.item.name == 'operations'):
            attempted.append(binop.loc)
        return original(binop, **kwargs)

    monkeypatch.setattr(check, '_tcr_index', index)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    assert attempted == []
    assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], timeout=10)
    assert result.returncode == 42


def test_implicit_zero_argument_result_keeps_index_interpretation(tmp_path):
    source = SrcFile(None, '''
make=():>array<int64 length=1>=>[42]
main=():>int64=>make[0]
''')
    output = tmp_path / 'zero-argument-index.udewy'
    output.write_text(codegen(source, debug_locations=False))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, debug_info=False)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], timeout=10)
    assert result.returncode == 42
