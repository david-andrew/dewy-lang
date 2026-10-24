"""A string-literal union alias imported from another file converts when called, and a name the file
does not see is attributed to the file that declares it, not to one that imports it or to this one."""
import subprocess

from tests.support import compiler  # noqa: F401


def run(compiler, source, command='run'):  # noqa: F811
    return subprocess.run([compiler, command, source], capture_output=True, text=True, timeout=60, check=False)


def test_imported_alias_call_converts(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'colors.dewy').write_text("Color:type = 'red' | 'green'\n")
    (tmp_path / 'show.dewy').write_text('from p"colors.dewy" import Color\nshow = (c:Color) => printl"shown {c}"\n')
    source = tmp_path / 'main.dewy'
    source.write_text('from p"colors.dewy" import Color\nfrom p"show.dewy" import show\n'
                      "let c = Color('red')\nmain = () => show(c)\n")
    ran = run(compiler, source)
    assert ran.returncode == 0 and ran.stdout == 'shown red\n', ran.stderr
    (tmp_path / 'qualified.dewy').write_text('import p"colors.dewy" as colors\n'
                                             "main = () => printl(colors.Color('green'))\n")
    ran = run(compiler, tmp_path / 'qualified.dewy')
    assert ran.returncode == 0 and ran.stdout == 'green\n', ran.stderr


def test_unseen_alias_names_its_declaring_file(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'colors.dewy').write_text("Color:type = 'red' | 'green'\n")
    (tmp_path / 'show.dewy').write_text('from p"colors.dewy" import Color\nshow = (c:Color) => printl"{c}"\n')
    source = tmp_path / 'main.dewy'
    source.write_text("from p\"show.dewy\" import show\nmain = () => show(Color('red'))\n")
    checked = run(compiler, source, 'check')
    assert checked.returncode != 0
    assert '`from p"colors.dewy" import Color` at its top' in checked.stderr, checked.stderr
    assert 'main.Color' not in checked.stderr, checked.stderr
