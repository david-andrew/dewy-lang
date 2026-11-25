"""Reader stores borrow original headers and retain unrelated parser state."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly

DRIVER = r'''use 'main.jo'
use 'reader_connect.dewy'
use 'dewy_reader_host.dewy'
use 'dewy_context.jo'
use 'dewy_reader_services.jo'
use 'dewy_nodes.jo'
use 'ast.jo'
use 'util.jo'
main = ():
    dc_parser.file = 77
    dc_parser.at = 99
    dc_parser.reader.dn_in_interpolation = 3
    assert(dc_reader_connect(&dc_parser, ParserReaderStores(&lists, &names, &dc_reader_host, &dw_builder_host)) and dc_reader_connect(&dc_parser, ParserReaderStores(&lists, &names, &dc_reader_host, &dw_builder_host)))
    assert(dc_parser.file == 77 and dc_parser.at == 99 and dc_parser.reader.dn_in_interpolation == 3)
    assert(dc_parser.stores.lists == &lists and dc_parser.stores.texts == &names)
    assert(dc_parser.stores.host == &dc_reader_host and dc_parser.stores.builder == &dw_builder_host)
    lists = [i32(123)]
    loop i in [0..512): lists.push(i32(i))
    assert(dc_parser.stores.lists[0].len() == 513 and dc_parser.stores.lists[0][512] == 511)
    lists = []
    assert(dc_parser.stores.lists[0].len() == 0)
    names = ["sentinel"]
    assert(dc_parser.stores.texts[0][0] == "sentinel")
    print("connected")
'''


def test_reader_connect_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    results = [subprocess.run([binary], capture_output=True, timeout=30)
               for binary in leaf_compilers(compiler, tmp_path, ('reader_connect',))]
    assert all(r.returncode == 0 for r in results), [r.stderr for r in results]
    assert results[0].stdout == results[1].stdout == b'connected\n'
