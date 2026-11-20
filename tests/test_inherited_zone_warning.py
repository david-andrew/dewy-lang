"""A helper reading the zone its callers set warns of none only when no file default exists."""
import subprocess

from tests.support import compiler  # noqa: F401 (fixture)

HELPER = """show = (text:string):>void => {
    let z = zoned(text)
    if z is? error return
    printl(z)
}
berlin = (text:string):>void => {
    $time.zone = 'Europe/Berlin'
    show(text)
}
main = () => {
    berlin("2026-10-28T14:15")
    show("2026-10-28T14:15")
}
"""
WARNING = '`zoned` has no time zone here'


def run(compiler, tmp_path, source):
    path = tmp_path / 'main.dewy'
    path.write_text(source)
    return subprocess.run([compiler, path], capture_output=True, text=True, timeout=300, check=False, cwd=tmp_path)


def test_file_default_reaches_helpers(compiler, tmp_path):
    ran = run(compiler, tmp_path, "$time.zone = 'UTC'\n" + HELPER)
    assert ran.returncode == 0, ran.stderr
    assert WARNING not in ran.stderr
    assert ran.stdout == '2026-10-28T14:15:00+01:00[Europe/Berlin]\n2026-10-28T14:15:00+00:00[UTC]\n'


def test_helper_without_default_warns(compiler, tmp_path):
    ran = run(compiler, tmp_path, HELPER)
    assert ran.returncode == 0, ran.stderr
    assert 'main.dewy:2:13: warning: ' + WARNING in ran.stderr
