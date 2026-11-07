"""The twelve-hour field `h` reads 1 to 12, in a constant and at run time."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)


@pytest.mark.parametrize('text,hms', [('1:15 AM', '01:15:00'), ('12:05 AM', '00:05:00'), ('12:05 PM', '12:05:00'),
                                      ('11:59 PM', '23:59:00')])
def test_valid_hours(compiler, tmp_path, text, hms):
    ran = run(compiler, tmp_path, f'printl(time_of_day("{text}" "h:mm a"))\n')
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == hms + '\n'


@pytest.mark.parametrize('text', ['13:15 AM', '0:15 AM', '00:15 PM'])
def test_other_hours(compiler, tmp_path, text):
    ran = run(compiler, tmp_path, f'printl(time_of_day("{text}" "h:mm a"))\n')
    assert ran.returncode != 0
    assert 'which `h` reads as 1 to 12' in ran.stderr
    ran = run(compiler, tmp_path, f'''f = (text:string) => {{
    let t = time_of_day(text "h:mm a")
    printl(if t is? ParseError {{t.message}} else {{"read"}})
}}
f("{text}")
''')
    assert ran.returncode == 0, ran.stderr
    assert 'which `h` reads as 1 to 12' in ran.stdout
