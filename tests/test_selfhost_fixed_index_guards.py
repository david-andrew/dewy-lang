"""The checker walk and its frozen twin agree on fixed-index guards and their fallback."""
import subprocess
from pathlib import Path

from tests import selfhost_lsp_double
from tests.selfhost_build_double import compare_builds
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


def test_fixed_index_guards_match_twins(compiler, tmp_path, monkeypatch):  # noqa: F811
    programs = sorted((ROOT / 'tests/cases/fixed_index_guards').glob('*.dewy'))
    results = compare_builds(compiler, tmp_path, monkeypatch, ('checker_indexes', 'checker_zonk', 'fixed_index'),
                             programs, flags=((), ('--release',)))
    for path, _, status, *_ in results:
        assert (status == 0) == (Path(path).stem == 'scoped')


# One checked subscript node can occur more than once in a body. Its child
# may be zonked between visits. Exercise the early flag before facts can run.
SHARED_INDEX = r'''use 'main.jo'
use 'fixed_index.dewy'
use 'ast.jo'
use 'node_store.dewy'
use 'check.jo'
use 'checker_state.dewy'
use 'type_ops.dewy'
use 'types.jo'
main = ():
    init_types()
    nodes = [Node()]
    locals = [Local(), Local(owner=1, type=i32(T_INT))]
    fns = [FnInst(), FnInst(locals=[1])]
    xs = mk(.ident, 0); nodes[xs].type = i32(mk_fixed(T_INT, 4))
    i = mk(.ident, 0); nodes[i].aux = 1; nodes[i].sym = 1
    index = mk(.index, 0); nodes[index].a = i32(xs); nodes[index].b = i32(i)
    loop first in [false, true]:
        loop second in [false, true]:
            clear_flag(index, NF_INBOUNDS)
            fi_owners[1] = true
            assert(fi_begin(1))
            fi_event(FI_OPEN)
            fi_refine(1, true, 4)
            nodes[i].type = i32(if first: T_INT else: 0)
            fi_index(index)
            nodes[i].type = i32(if second: T_INT else: 0)
            fi_index(index)
            fi_finish()
            assert(has_flag(index, NF_INBOUNDS) == (first and second))
    print("shared visits agree")
'''


def test_shared_fixed_index_requires_every_visit(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', SHARED_INDEX)
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('fixed_index',)):
        run = subprocess.run([binary], capture_output=True, timeout=60)
        assert run.returncode == 0, run.stderr
        assert run.stdout == b'shared visits agree\n'
