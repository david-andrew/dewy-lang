"""lower_group keeps runtime output uncancelable with both compiler leaves."""
import pytest
from tests.support import ROOT, compiler
from tests.selfhost_build_double import compare_builds
from tests.selfhost_lsp_double import leaf_compilers
import subprocess


@pytest.mark.core_quick
def test_output_cancellation_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_EMIT_WORKERS', '1')
    files = ['tests/cases/tasks/output_canceled.dewy']
    compare_builds(compiler, tmp_path, monkeypatch, ('lower_group',), files, flags=((), ('--release',)))
    for binary in leaf_compilers(compiler, tmp_path, ('lower_group',)):
        for flags in ((), ('--release',)):
            output = tmp_path / 'output'
            built = subprocess.run([binary, 'build', ROOT / files[0], '-o', output, *flags], capture_output=True, timeout=120)
            assert built.returncode == 0, built.stderr
            ran = subprocess.run([output], capture_output=True, timeout=10)
            assert (ran.returncode, ran.stdout, ran.stderr) == (0, b'inside canceled group\nchild\ndone\n', b'')
