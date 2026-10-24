"""Several values passed to a call: a warning when positional arguments follow a value
whose count is not written at the call, and inlay hints naming the parameters they fill."""
import subprocess

from tests.support import compiler  # noqa: F401
from tests.test_core_editor_features import Client, compiler_path, position

SOURCE = '''add3 = (a:int64 b:int64 c:int64) => a + b + c
pair = ():>(int64 int64) => { 1 2 }
main = () => {
    printl(add3(pair() 3))
    printl(add3(3 pair()))
    printl(add3((1 2) 3))
}
'''


def test_values_followed_by_positional_arguments_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    warnings = [line for line in checked.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == 1, checked.stderr
    assert ':4:17:' in warnings[0] and "'pair()' gives 2 values, filling as many positions" in warnings[0], warnings


def test_values_inlay_hints_name_the_parameters(tmp_path):
    path = tmp_path / 'main.dewy'
    path.write_text(SOURCE)
    client = Client(compiler_path(), tmp_path)
    try:
        client.set_text(path.as_uri(), SOURCE, 1)
        hints = client.request('textDocument/inlayHint', {
            'textDocument': {'uri': path.as_uri()},
            'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': 99, 'character': 0}}})
    finally:
        client.close()
    labels = [(h['position'], h['label']) for h in hints]
    assert (position(SOURCE, 'pair() 3'), 'a b:') in labels, labels
    assert (position(SOURCE, 'pair()))'), 'b c:') in labels, labels
