"""Name interning and source positions agree with the frozen Jo utility functions."""

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly


SERVICES = '''use 'source_types.dewy'
files: SrcFile[]
lib_root = ""
names: str[]
name_hash: int[]
name_tab: i32[]
'''

DRIVER = '''main = ():
    raw = read_file(args()[1]) ?? ""
    assert(util_intern("") == 0 and not util_name_known(raw))
    id = util_intern_sub(raw, 1, len(raw) - 2)
    assert(id == 1 and util_name_of(id) == raw[1..len(raw)-1))
    assert(util_name_known(util_name_of(id)) and not util_name_known(raw))
    assert(util_intern(util_name_of(id)) == id)
    whole = util_intern_new(raw, 0, len(raw), hash_bytes(data(raw), len(raw)))
    assert(whole == 2 and util_name_of(whole) == raw and util_name_known(raw))
    files = [SrcFile(path="/src/main.dewy"), SrcFile(path="/lib/module.dewy")]
    loc = util_mkpos(1, 17)
    assert(not util_pos_in_lib(loc))
    lib_root = "/lib/"
    assert(util_pos_in_lib(loc) and not util_pos_in_lib(17))
    assert(not util_pos_in_lib(-1) and not util_pos_in_lib(util_mkpos(2, 0)))
    assert(util_pos_file(loc) == 1 and util_pos_off(loc) == 17)
    assert(util_pos_file(-1) == -1 and util_pos_off(-1) == 0xFFFFFFFFFF)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_util_ops_twins(compiler, tmp_path, release):
    source = tmp_path / 'bytes'
    source.write_bytes(b'!\xff\x00\xc0?')
    assert compare_narrow(compiler, tmp_path, release, ('source_types', 'util_ops'), DRIVER,
                          doubles={'services.jo': SERVICES}, services=('util',),
                          invocations=(((str(source),), 0),)) == b'ok\n'
