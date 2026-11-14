"""Semicolon spacing has no effect on array dimensions (decisions.md batch 6)."""
import os
import subprocess
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401
from tests.test_core_editor import Client

SOURCE = """f=()=>5
main=()=>{
    printl([1 2; 3 4])
    printl([f(); 7])
    printl([1 2 ; 3 4])
}
"""


def test_attached_row_is_a_separator(compiler, tmp_path):
    source = tmp_path / 'main.dewy'
    source.write_text(SOURCE)
    run = subprocess.run([compiler, source], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout == '[1 2; 3 4]\n[5 7]\n[1 2; 3 4]\n'
    assert 'warning:' not in run.stderr


def test_attached_row_has_no_obsolete_quickfix(tmp_path):
    value = os.environ.get('DEWY_CORE_COMPILER')
    if not value:
        pytest.skip('set DEWY_CORE_COMPILER for the editor checks')
    source = tmp_path / 'main.dewy'
    source.write_text('main=():>void=>exit(0)')
    client = Client(Path(value).resolve(strict=True), tmp_path)
    try:
        text = 'main=()=>{\n    printl([1 2; 3 4])\n}\n'
        diagnostics = client.set_text(source.as_uri(), text, 1)
        assert not [d for d in diagnostics if d['severity'] in (1, 2)], diagnostics
        actions = client.request('textDocument/codeAction', {
            'textDocument': {'uri': source.as_uri()},
            'range': {'start': {'line': 1, 'character': 15}, 'end': {'line': 1, 'character': 16}},
            'context': {'diagnostics': diagnostics},
        })
        assert not [a for a in actions if 'row break' in a['title']], actions
    finally:
        client.close()
