"""A "did you mean" hint names only what the program can call: a library function that Dewy
does not see (the Sloppy `eprint`) is never suggested, and a visible near name still is."""
import subprocess

from tests.support import compiler  # noqa: F401


def check(compiler, source):  # noqa: F811
    return subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)


def test_hidden_function_is_not_suggested(compiler, tmp_path):  # noqa: F811
    for call in ('eprintl"x"', 'eprint("x")', 'eprintt("x")'):
        source = tmp_path / 'main.dewy'
        source.write_text(f'main = () => {{\n    {call}\n}}\n')
        checked = check(compiler, source)
        assert checked.returncode != 0
        assert "did you mean 'eprint'" not in checked.stderr, checked.stderr


def test_visible_near_name_is_still_suggested(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text('main = () => {\n    prnit("x")\n}\n')
    checked = check(compiler, source)
    assert checked.returncode != 0 and "did you mean 'print'" in checked.stderr, checked.stderr
