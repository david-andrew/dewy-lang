"""A civil step from before 1972, under UTC's old rates, in a constant and at run time."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)


@pytest.mark.parametrize('start,after', [('1961-01-01T00:00:00', '1961-01-02T00:00:00'),
                                         ('1965-01-01T12:00:00', '1965-01-02T12:00:00'),
                                         ('1970-01-01T12:00:00', '1970-01-02T12:00:00')])
def test_day_step(compiler, tmp_path, start, after):
    ran = run(compiler, tmp_path, f'const a=zoned"{start}[UTC]"\nprintl(a+1day)\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'{after}+00:00[UTC]\n'
    ran = run(compiler, tmp_path, f'f=(s:string)=>{{let a=zoned(s zone=zone"UTC") if a is? ZonedDateTime '
                                  f'{{printl(a+1day)}}}}\nf("{start}")\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == f'{after}+00:00[UTC]\n'


def test_a_month_step_keeps_the_time_of_day(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'const a=zoned"1970-01-01T12:00:00[UTC]"\nprintl(a+1month)\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '1970-02-01T12:00:00+00:00[UTC]\n'


def test_local_mean_time_offsets_print_and_read_their_seconds(compiler, tmp_path):
    ran = run(compiler, tmp_path, 'printl(zoned"1961-06-01T12:00:00[Africa/Monrovia]")\n'
                                  'printl(zoned"1961-06-01T12:00:00-00:44:30[Africa/Monrovia]")\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == '1961-06-01T12:00:00-00:44:30[Africa/Monrovia]\n' * 2
