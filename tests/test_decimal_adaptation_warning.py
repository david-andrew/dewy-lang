"""A decimal binding that a later float write makes float64 warns at each exact comparison
reading it (`=?`, `not=?`, where the change can flip the result), with an editor fix-it
annotating its declaration `float64`; annotated bindings and adaptation without an exact
comparison stay quiet."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

MESSAGE = 'so this exact comparison tests float64 values'

ADAPTED = '''let rate=0.1
main=()=>{
    let tax=0.3
    let f:float64=0.1
    printl(tax =? 0.3)
    tax=f*3
    printl(tax not=? 0.3)
    rate+=f
    printl(rate*2 =? 0.4)
}
'''

QUIET = '''main=()=>{
    let total=0.0
    let stated:float64=0.3
    let exact=0.1
    let f:float64=0.1
    loop _ in [0..3) total+=f
    stated=f*3
    exact+=0.2
    printl"{total} {stated =? 0.3} {exact =? 0.3}"
}
'''


def warnings_of(compiler, path):  # noqa: F811
    checked = subprocess.run([compiler, 'check', path], capture_output=True, text=True,
                             timeout=60, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    return [line for line in checked.stderr.splitlines() if MESSAGE in line]


def test_comparisons_of_adapted_decimals_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(ADAPTED)
    found = warnings_of(compiler, source)
    places = sorted((int(line.split(':')[-4]), int(line.split(':')[-3])) for line in found)
    assert places == [(5, 12), (7, 12), (9, 12)], found
    assert any('`tax` is float64 because of the float written to it at line 6' in line for line in found)
    assert any('`rate` is float64 because of the float written to it at line 8' in line for line in found)
    assert all('annotate `float64` (or another explicit representation)' in line for line in found)


def test_stated_or_uncompared_bindings_do_not_warn(compiler, tmp_path):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(QUIET)
    assert warnings_of(compiler, source) == []


def test_adaptation_quickfix(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    text = 'main=()=>{\n    let tax=0.3\n    let f:float64=0.1\n    tax=f*3\n    printl(tax =? 0.3)\n}\n'
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        diagnostics = client.set_text(source.as_uri(), text, 1)
        warnings = [d for d in diagnostics if d['severity'] == 2 and MESSAGE in d['message']]
        assert len(warnings) == 1, diagnostics
        assert warnings[0]['range']['start'] == {'line': 4, 'character': 11}, warnings
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()}, 'range': warnings[0]['range'],
            'context': {'diagnostics': warnings},
        })
        assert len(actions) == 1, actions
        edits = actions[0]['edit']['changes'][source.as_uri()]
        at = {'line': 1, 'character': 11}
        assert edits == [{'range': {'start': at, 'end': at}, 'newText': ':float64'}], edits
        fixed = text.replace('let tax=', 'let tax:float64=')
        diagnostics = client.set_text(source.as_uri(), fixed, 2)
        assert not [d for d in diagnostics if MESSAGE in d['message'] or d['severity'] == 1], diagnostics
    finally:
        client.close()
