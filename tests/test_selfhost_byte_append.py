"""Raw byte appends preserve contents and shared-array ownership across the twin."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'byte_append.dewy'
main = ():
    out: u8[] = [0, 255]
    shared = out
    append_bytes(mut out, [])
    print("empty:{out.len()}:{shared.len()}")
    small: u8[] = [1, 128]
    append_bytes(mut out, small)
    print("copy:{out.len()}:{shared.len()}:{int(out[2])}:{int(out[3])}")
    append_bytes(mut out, out)
    print("self:{out.len()}:{int(out[4])}:{int(out[5])}:{int(out[7])}")
    source: u8[] = []
    loop i in [0..4096): source.push(u8(i % 256))
    append_bytes(mut out, source)
    print("large:{out.len()}:{int(out[8])}:{int(out[4103])}:{source.len()}")
    blank: u8[] = []
    append_bytes(mut blank, source)
    print("blank:{blank.len()}:{int(blank[4095])}")
'''


def test_byte_append_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('byte_append',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == (b'empty:2:2\ncopy:4:2:1:128\nself:8:0:255:128\n'
                                 b'large:4104:0:255:4096\nblank:4096:255\n')
