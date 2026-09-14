"""Decimal interpolation preserves every signed and unsigned word's value."""
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_integer_interpolation_limits(tmp_path, target):
    cases = [(f'int{bits}', -(1 << (bits - 1))) for bits in (8, 16, 32, 64)]
    cases += [(f'uint{bits}', (1 << bits) - 1) for bits in (8, 16, 32, 64)]
    cases += [('int64', -1), ('int64', 0), ('int64', (1 << 63) - 1), ('uint64', 1 << 63)]
    parameters = ' '.join(f'n{i}:{type_}' for i, (type_, _) in enumerate(cases))
    fields = ':'.join(f'{{n{i}}}' for i in range(len(cases)))
    arguments = ' '.join(f'({value})' if value < 0 else str(value) for _, value in cases)
    expected = ':'.join(str(value) for _, value in cases)
    source = tmp_path / 'limits.dewy'
    source.write_text(f'let format=({parameters}):>string=>"{fields}"\n'
                      f'let main=():>int64=>if format({arguments})=?"{expected}" 42 else 1\n')
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), target=target))
    assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10)
    assert result.returncode == 42, result.stdout + result.stderr
