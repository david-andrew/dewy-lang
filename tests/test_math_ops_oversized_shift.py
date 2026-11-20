import subprocess

import pytest

from tests.selfhost_facts_double import compare_facts
from tests.support import ROOT, compiler  # noqa: F401


CASE = 'exact_int/oversized_word_shift'


def test_math_ops_twins_oversized_word_shift(compiler, tmp_path, monkeypatch):
    assert compare_facts(compiler, tmp_path, monkeypatch, [CASE], leaves=('math_ops',)) == 1


@pytest.mark.parametrize('flags', [(), ('--release',), ('--target', 'web'), ('--target', 'web', '--release')])
def test_oversized_shift_across_integer_widths(compiler, tmp_path, flags):
    source = tmp_path / 'shifts.dewy'
    source.write_text('''$runtime_checks
from p"word.dewy" import (main as word)

shift = <T>(positive:T negative:T n:int64):>void => {
    printl(positive >> n negative >> n positive << n)
    let left = positive
    let right = negative
    left <<= n
    right >>= n
    printl(left right)
}

main = ():>void => {
    word()
''' + '\n'.join(
        f"    shift({ty}<overflow='wrap'>(1) {ty}<overflow='wrap'>({value}) {count})"
        for bits in (8, 16, 32, 64)
        for ty, value in ((f'int{bits}', -2), (f'uint{bits}', 2 ** bits - 1))
        for count in sorted({bits, 64, 65})
    ) + '\n}\n')
    case = ROOT / 'tests/cases' / CASE
    (tmp_path / 'word.dewy').write_text(case.with_suffix('.dewy').read_text())
    result = subprocess.run([compiler, 'run', source, *flags], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    expected = case.with_suffix('.out').read_text()
    for bits in (8, 16, 32, 64):
        repeats = 2 if bits == 64 else 3
        expected += '0 -1 0\n0 -1\n' * repeats + '0 0 0\n0 0\n' * repeats
    assert result.stdout == expected
