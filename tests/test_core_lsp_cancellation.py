"""Each running-checker cancellation scenario is independent and schedulable."""
import shutil
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

SCENARIOS = [
    'cancel-textDocument/hover', 'cancel-textDocument/completion',
    'cancel-textDocument/prepareRename', 'changed',
    'abandoned-textDocument/didChange', 'abandoned-textDocument/didClose',
    'eof', 'fragment-header', 'fragment-body',
]


@pytest.mark.parametrize('scenario', [
    pytest.param(name, marks=pytest.mark.xdist_group(name=f'lsp-cancellation-{name}'))
    for name in SCENARIOS
])
def test_vscode_core_client_cancellation(compiler, tmp_path, scenario):  # noqa: F811
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed for the editor client')
    result = subprocess.run([node, ROOT / 'tests/fixtures/core_editor/cancellation.cjs',
                             compiler, tmp_path, scenario], capture_output=True,
                            text=True, timeout=50, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'running cancellation, changed text, parser state and fragmented frames passed' in result.stdout
