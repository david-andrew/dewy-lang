"""Global symbol allocation preserves IDs, module ownership and generated names."""
import subprocess

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = """use 'main.jo'
use 'check.jo'
use 'checker_global_instances.dewy'
use 'util.jo'
main = ():
    name = intern("count")
    inst_counter = 12
    a = new_global(name, 17, 2)
    b = new_global(name, 21, 3)
    print("{b == a + 1}:{global_ids[0] == a}:{global_ids[1] == b}")
    print("{globals[a].sym}:{globals[a].decl}:{globals[a].mod}")
    print("{globals[b].sym}:{globals[b].decl}:{globals[b].mod}:{inst_counter}")
"""


def test_checker_global_instances_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_global_instances',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert result.stdout == b'true:true:true\ng_count_13:17:2\ng_count_14:21:3:14\n'
