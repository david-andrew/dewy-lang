"""dump_host_values in host_ir_values preserves the frozen twin's host-IR words and bytes."""
import subprocess

import pytest

from tests import selfhost_lsp_double
from tests.selfhost_build_double import build_all
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_host_ir import PROGRAM, pytestmark

DRIVER = '''use 'main.jo'
use 'host_ir_values.dewy'
main = ():
    if args().len() > 1 and args()[1] == "dump-values":
        empty: int[]
        words: int[] = [-9223372036854775807 - 1, -1, 0, 9223372036854775807]
        bytes: u8[] = [0, 1, 127, 128, 255]
        narrow: i8[] = [-128, -1, 0, 127]
        slots: i32[] = [-2147483647 - 1, -1, 0, 2147483647]
        bits: u64[] = [0, u64(9223372036854775807), u64(0) - u64(1)]
        dump_host_values("EMPTY", empty)
        dump_host_values("ROOTS", words)
        dump_host_values("DATA", bytes)
        dump_host_values("I8", narrow)
        dump_host_values("I32", slots)
        dump_host_values("BITS", bits)
    else:
        lower_test_cli()
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_host_ir_values_match_twin(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('host_ir_values',))
    outputs = [subprocess.run([b, 'dump-values'], capture_output=True, timeout=30)
               for b in binaries]
    assert all(p.returncode == 0 and not p.stderr for p in outputs)
    expected = (b'EMPTY []\nROOTS [-9223372036854775808, -1, 0, 9223372036854775807]\n'
                b'DATA [0, 1, 127, 128, 255]\nI8 [-128, -1, 0, 127]\n'
                b'I32 [-2147483648, -1, 0, 2147483647]\nBITS [0, 9223372036854775807, -1]\n')
    assert outputs[0].stdout == outputs[1].stdout == expected
    (tmp_path / 'host.dewy').write_text(PROGRAM)
    results = [build_all(b, tmp_path, label, ['host.dewy', ROOT / 'examples/ring.dewy'],
                         flags=(('--host-ir',), ()))
               for b, label in zip(binaries, ('dewy', 'jo'))]
    assert results[0] == results[1]
    for _, flags, status, out, err, _ in results[0]:
        assert status == 0
        if flags:
            assert out.startswith('DEWY_HOST_IR 1\n')
            assert '\nROOTS [' in out and '\nDATA [' in out and '\nKV [' in out
