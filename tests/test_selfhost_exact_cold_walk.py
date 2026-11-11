"""Exact mark growth and shader call traversal agree with frozen Jo."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'exact_cold_walk.dewy'
use 'exact.jo'
use 'ast.jo'
use 'node_store.dewy'
main = ():
    exact_marks = []
    exact_reserve(0); exact_marks[3] = 23
    print("reserve:{exact_marks.len()}")
    exact_reserve(63); print("same:{exact_marks.len()}")
    exact_reserve(64); print("grow:{exact_marks.len()}:{exact_marks[3]}")
    exact_reserve(-1); print("negative:{exact_marks.len()}")
    nodes = [Node()]
    first = mk(.call, 0); nodes[first].sym = 7
    next = mk(.call, 0); nodes[next].sym = 8; nodes[first].a = i32(next)
    ignored = mk(.call, 0); nodes[ignored].sym = 9
    closure = mk(.lambda, 0); nodes[closure].b = i32(ignored)
    special = mk(.call, 0); nodes[special].sym = 10; nodes[special].aux = 1; set_list(special, [next])
    block = mk(.block, 0); set_list(block, [first, closure, special])
    work: int[] = [99]
    exact_shader_calls(0, mut work)
    exact_shader_calls(block, mut work)
    print("calls:{work}")
'''


def test_exact_cold_walk_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('exact_cold_walk',))
    outputs = [subprocess.run([b], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == b'reserve:64\nsame:64\ngrow:192:23\nnegative:192\ncalls:[99, 7, 8, 8]\n'
