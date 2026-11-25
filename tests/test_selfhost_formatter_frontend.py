"""Formatter token signatures, comment snapshots and failures agree across frontend twins."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_formatter_frontend_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    binaries = leaf_compilers(compiler, tmp_path, ('formatter_frontend',))
    inputs = [b'', b'main=()=>{let x=1\nprintl(x)}\n',
              b'# tail\nmain = () => {\n # nested #{block}#\n printl("{1}")\n}\n',
              'main=()=>{let é="café"\nprintl(é)}\n'.encode(),
              b'main=()=>{printl("unterminated)\n', b'main=()=>{(}\n',
              b'# malformed byte in comment \xff\nmain=()=>{}\n']
    for source in inputs:
        results = [subprocess.run([binary, 'fmt', '-'], input=source, capture_output=True, timeout=60)
                   for binary in binaries]
        assert (results[0].returncode, results[0].stdout, results[0].stderr) == (
            results[1].returncode, results[1].stdout, results[1].stderr), source
    assert results[0].returncode == 0
