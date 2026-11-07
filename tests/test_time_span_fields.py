"""Span's years, months and days against dates counted by hand, on the anniversary rule `age` uses."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

CASES = [('2000-02-29', '2027-03-01', '27 0 0'), ('2000-02-29', '2027-03-02', '27 0 1'),
         ('2000-02-29', '2027-02-28', '26 11 30'), ('2000-02-29', '2028-02-29', '28 0 0'),
         ('2024-02-29', '2025-03-01', '1 0 0'), ('2024-02-29', '2024-03-29', '0 1 0'),
         ('2024-10-24', '2026-12-25', '2 2 1'), ('2025-01-31', '2025-03-01', '0 1 1'),
         ('2025-01-29', '2025-03-01', '0 1 1'), ('2027-03-01', '2000-02-29', '-27 0 0')]


@pytest.mark.parametrize('early,late,fields', CASES)
def test_fields(compiler, tmp_path, early, late, fields):
    path = tmp_path / 'main.dewy'
    path.write_text(f'let s=date"{late}"-date"{early}"\nprintl"{{s.years}} {{s.months}} {{s.days}}"\n')
    ran = subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == fields + '\n'
