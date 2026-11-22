"""A compilation resets previously used exact storage and expires positive bounds again."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r"""use 'main.jo'
use 'exact.jo'
use 'exact_lifecycle.dewy'
use 'facts.jo'
use 'exact_reset_loop.jo'
use 'driver_cli.dewy'
use 'util.jo'
use 'check.jo'
main = ():
    lib_dir = find_lib_dir()
    lib_root = lib_dir
    lower_only = true
    loop i in [1..3):
        old = positive_epoch
        exact_widths = [123]
        saved = exact_widths
        exact_owners[9999999] = true
        exr_fast = true
        exr_call_target = 987
        if i == 1: exact_reset()
        else: compile(args()[1], "")
        assert(positive_epoch > old)
        assert(saved == [123] and exact_widths != saved)
        assert(not exact_owners.has(9999999))
        assert(not exr_fast and exr_call_target != 987)
        print("reset:{i}")
"""


def test_exact_lifecycle_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    source = tmp_path / 'program.dewy'
    source.write_text('printl(2)\n')
    for binary in leaf_compilers(compiler, tmp_path, ('exact_lifecycle',)):
        run = subprocess.run([binary, source], capture_output=True, timeout=60)
        assert (run.returncode, run.stdout) == (0, b'reset:1\nreset:2\n'), run.stderr
