"""An indexed store follows member routes back to the original borrow."""

import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('source', [
    'let rows=[[values=[1]]]\nloop row in rows {row.values[0]=7}',
    "let rows=['a' -> [values=[1]]]\nloop [key row] in rows {row.values[0]=7}",
    'const row=[values=[1]]\nrow.values[0]=7',
])
def test_indexed_member_stores_reject_read_only_roots(source):
    with pytest.raises(UserError, match='cannot mutate an element of a const array'):
        check._typecheck_module(SrcFile(None, source))


def test_copying_a_borrowed_record_allows_an_independent_element_store(tmp_path):
    source = '''
let main=():>int64=>{
    let rows=[[values=[1]]]
    loop row in rows {
        let owned=row
        owned.values[0]=7
        printl(owned.values[0])
    }
    printl(rows[0].values[0])
    return 0
}
'''
    output = tmp_path / 'indexed_copy.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['7', '1']
