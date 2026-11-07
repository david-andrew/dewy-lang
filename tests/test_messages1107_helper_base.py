"""A helper's confinement warning names the base its caller joined the path onto."""
import subprocess

from tests.support import compiler  # noqa: F401

HELPER = '''count = (file:Path) => (file.read_text or_throw).length
main = () => {
    let input = p("data")
    loop name in (input.list or_throw) {
        printl(count(p"{input}/{name}") or_throw)
    }
}
'''


def test_helper_warning_names_the_callers_base(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(HELPER)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert ('1:25: warning: `file` may escape its base (built from unproven text on line 5): '
            'validate it, `input.confine(file) or_throw`, or test it first, '
            '`if input.contains(file) {...}`') in checked.stderr, checked.stderr
