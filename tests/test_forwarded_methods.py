"""`r.m(a)` on a value-or-error union finds m as a method of the value's own type."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path)


def test_parsed_date_formats_and_errors_pass_through(compiler, tmp_path):
    source = '''f=(s:string)=>printl(date(s).format("yyyy-MM-dd"))
f("2024-02-29")
f("not a date")
'''
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    lines = ran.stdout.splitlines()
    assert lines[0] == '2024-02-29'
    assert lines[1].startswith('ParseError')


def test_other_parsed_times(compiler, tmp_path):
    source = '''t=(s:string)=>printl(time_of_day(s).format("HH:mm"))
l=(s:string)=>printl(local(s).format("yyyy-MM-dd HH:mm"))
i=(s:string)=>printl(instant(s).format("yyyy-MM-dd HH:mm"))
t("12:30:00")
l("2024-02-29T12:30:00")
i("2024-02-29T12:30:00Z")
'''
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['12:30', '2024-02-29 12:30', '2024-02-29 12:30']


def test_a_user_module_method_with_a_named_argument(compiler, tmp_path):
    (tmp_path / 'shapes.dewy').write_text('''Square:type=[side:int64]
read=(text:string):>Square?=>if text =? "two" {Square[2]} else {none}
describe=(s:Square label:string="x"):>string=>"{label}{s.side}"
''')
    source = '''from p"shapes.dewy" import read
f=(text:string)=>printl(read(text).describe(label="side "))
f("two")
f("other")
'''
    ran = run(compiler, tmp_path, source)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines()[0] == 'side 2'
    assert ran.stdout.splitlines()[1] == 'none'
