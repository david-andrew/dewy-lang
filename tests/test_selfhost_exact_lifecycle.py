"""Two successful check requests reset exact storage and expire the preceding cache epoch."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


DRIVER = r"""use 'main.jo'
use 'exact.jo'
use 'exact_lifecycle.dewy'
use 'facts.jo'
use 'exact_reset_loop.jo'
use 'driver_cli.dewy'
use 'driver_compile.dewy'
use 'util.jo'
use 'check.jo'
request = (path: str, marker: int) -> int:
    previous = positive_epoch
    exact_widths = [marker]
    retained = exact_widths
    exact_owners[9999999] = true
    exr_fast = true
    exr_call_target = 987
    compile(path, "")
    assert(positive_epoch > previous)
    assert(retained == [marker] and exact_widths != retained)
    assert(not exact_owners.has(9999999))
    assert(not exr_fast and exr_call_target != 987)
    positive_epoch

main = ():
    lib_dir = find_lib_dir()
    lib_root = lib_dir
    lower_only = true
    # Use the interactive host's snapshot to restore unrelated compiler globals.
    # Keep the completed request's exact/fact epoch across the restore.
    lo, size = __image_data()
    snapshot = __snap_take(lo, lo + size)
    first = request(args()[1], 123)
    __snap_restore(snapshot)
    __snap_drop(snapshot)
    positive_epoch = first
    assert(request(args()[2], 456) > first)
    print("two requests ok")
"""


def test_exact_lifecycle_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    sources = []
    for i in (2, 3):
        source = tmp_path / f'program{i}.dewy'
        source.write_text(f'printl({i})\n')
        sources.append(source)
    for binary in leaf_compilers(compiler, tmp_path, ('exact_lifecycle',)):
        run = subprocess.run([binary, *sources], capture_output=True, timeout=60)
        assert (run.returncode, run.stdout) == (0, b'two requests ok\n'), run.stderr
