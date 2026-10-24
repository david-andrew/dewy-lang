"""`[1 2; 3 4]` is valid: the attached `;` discards the 2, giving `[1 3 4]`. Discarding a value
that does nothing looks like a mistaken row break, so it warns, with an editor fix-it that
makes it a standalone ` ;`."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

MESSAGE = 'this `;` is attached to the value before it'

SOURCE = '''f=()=>5
main=()=>{
    printl([1 2; 3 4])
    printl([f(); 7])
    printl([1 2 ; 3 4])
}
$runtime_checks
'''


def test_attached_row_discards_and_warns(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    run = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout == '[1 3 4]\n[7]\n[1 2; 3 4]\n', run.stdout
    warnings = [line for line in run.stderr.splitlines() if 'warning:' in line]
    assert len(warnings) == 1, run.stderr
    assert ':3:15:' in warnings[0] and MESSAGE in warnings[0] and '`[1 2 ; 3 4]`' in warnings[0], warnings


def test_attached_row_quickfix(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    text = 'main=()=>{\n    printl([1 2; 3 4])\n}\n'
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and MESSAGE in d['message']]
        assert len(warnings) == 1, diagnostics
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': warnings[0]['range'],
            'context': {'diagnostics': warnings},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        at = {'line': 1, 'character': 15}
        assert edits == [{'range': {'start': at, 'end': at}, 'newText': ' '}], edits
        diagnostics = client.set_text(source.as_uri(), text.replace('2;', '2 ;'), 2)
        assert not [d for d in diagnostics if MESSAGE in d['message'] or d['severity'] == 1], diagnostics
    finally:
        client.close()
