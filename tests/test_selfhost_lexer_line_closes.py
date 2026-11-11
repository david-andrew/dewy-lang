"""Byte-oriented legacy line lookahead agrees with its frozen Jo implementation."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'lexer_line_closes.dewy'
use 'lex.jo'
lx_line_case = (input: int[], start: int, expected: bool):
    bytes: u8[] = []
    loop value in input: bytes.push(u8(value))
    lx_p = data(bytes); lx_n = bytes.len()
    got = lx_line_closes(start)
    print("case:{got == expected}")
main = ():
    lx_line_case([], 0, false)
    lx_line_case([41], 0, true)
    lx_line_case([93], 0, true)
    lx_line_case([125], 0, true)
    lx_line_case([40, 41], 0, false)
    lx_line_case([91, 93, 41], 0, true)
    lx_line_case([123, 125], 0, false)
    lx_line_case([40, 120, 41, 58], 0, true)
    lx_line_case([32, 9, 40, 41, 32, 45, 62, 32, 84, 58, 13], 0, true)
    lx_line_case([120, 58], 0, false)
    lx_line_case([40, 58], 0, false)
    lx_line_case([40, 41, 58, 35, 41], 0, true)
    lx_line_case([35, 41], 0, false)
    lx_line_case([10, 41], 0, false)
    lx_line_case([120, 41], 1, true)
    lx_line_case([255, 0, 128, 41], 0, true)
    lx_line_case([255, 0, 128], 0, false)
    lx_line_case([34, 41, 34], 0, false)
    lx_line_case([39, 93, 39, 41], 0, true)
    lx_line_case([34, 92, 34, 41, 34], 0, false)
    lx_line_case([114, 34, 92, 34, 41], 0, true)
    lx_line_case([34, 34, 34, 41, 34, 34, 34], 0, false)
    lx_line_case([34, 123, 34, 41, 34, 125, 34], 0, false)
    lx_line_case([34, 41], 0, false)
    lx_line_case([39, 41], 0, false)
    lx_line_case([34, 34, 34, 41], 0, false)
    lx_line_case([40, 41, 58, 32, 9, 13, 10, 41], 0, true)
'''


def test_lexer_line_closes_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_line_closes',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == b'case:true\n' * 27
