"""Diagnostic text, quiet errors and mapped exit statuses agree with the frozen twin."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'util.jo'
use 'diagnostic_exit.dewy'
main = ():
    error_exit = 17
    op = args()[1]
    if op == "fatal": fatal(-1, "round76")
    if op == "quiet":
        quiet_errors = true
        fatal(-1, "round76")
    if op == "ice": ice("round76")
    if op == "mapped": stop(1)
    print("ok")
    stop(0)
'''


def test_diagnostic_exit_matches_twin(compiler, tmp_path, monkeypatch):
    paths = [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests/cases/errors').glob('*.dewy'))]
    compare_builds(compiler, tmp_path, monkeypatch, ('diagnostic_exit',), paths)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('diagnostic_exit',))
    for op, code, message in [('fatal', 17, b'error: round76'), ('quiet', 17, b''),
                              ('ice', 2, b'internal compiler error: round76'), ('mapped', 17, b''), ('ok', 0, b'')]:
        results = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in results), [(r.returncode, r.stderr) for r in results]
        assert (results[0].stdout, results[0].stderr) == (results[1].stdout, results[1].stderr)
        assert message in results[0].stderr
        if op in ('quiet', 'mapped'): assert results[0].stderr == b''
