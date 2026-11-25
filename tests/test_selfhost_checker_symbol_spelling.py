"""Generated symbols preserve ASCII names, fixed-length bounds and operator spellings."""
import subprocess

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

DRIVER = """use 'main.jo'
use 'checker_symbol_spelling.dewy'
main = ():
    loop name in ["", "alpha9", "[]=", "?", "_first", "ab-c", "aéz", "abcdefghijklmnopqrstuvwxyz0123456789ABCDE", "abcdefghijklmnopqrstuvwxyz0123456789ABCDEF"]: print(sanitize(name))
"""


def test_checker_symbol_spelling_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    limit = b'abcdefghijklmnopqrstuvwxyz0123456789ABCDE\n'
    expected = b'\nalpha9\nop_set\nop\n_first\nabXc\naXXz\n' + limit * 2
    for binary in selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('checker_symbol_spelling',)):
        result = subprocess.run([binary], check=True, capture_output=True, timeout=60)
        assert result.stdout == expected
