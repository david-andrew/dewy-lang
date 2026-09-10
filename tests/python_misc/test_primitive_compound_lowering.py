"""Primitive updates use the same target operations as ordinary expressions."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('type_, initial, operator, operand, expected', [
    ('int64', 6, '&', 3, 2),
    ('int64', 6, '|', 3, 7),
    ('int64', 6, 'xor', 3, 5),
    ('int64', 6, 'nand', 3, -3),
    ('uint8', 250, '+', 10, 4),
    ('uint8', 1, '-', 2, 255),
    ('int8', 120, '+', 10, -126),
    ('uint64', 18446744073709551615, '//', 2, 9223372036854775807),
])
def test_primitive_compound_operation(tmp_path, type_, initial, operator, operand, expected):
    output = tmp_path / 'compound.udewy'
    source = f'''let main=():>int64=>{{
        let value:{type_}={initial}
        value {operator}= {operand}
        printl(value)
        return 0
    }}'''
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'{expected}\n'
