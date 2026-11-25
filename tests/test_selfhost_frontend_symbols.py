"""Every byte class and punctuation slot agrees with the frozen enum-ordinal constructor."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = '''use 'dewy_tokens.dewy'
dn_classes: u8[]
dn_symbols: DewyToken[]
lx_cls: *u8 = null
base_classes: u8[]
dn_ident_start = (c: u8) -> bool: is_alpha(c) or c == 95 or c >= 128
'''
DRIVER = r'''main = ():
    base_classes = fill(u8(0), 256)
    loop c in [0..256): base_classes[c] = u8(c & 3)
    lx_cls = data(base_classes)
    frontend_symbols_bind(&dn_classes as *int, &dn_symbols as *int)
    dn_init_symbols()
    assert(dn_classes.len() == 256 and dn_symbols.len() == 16384)
    assert(dn_classes[48] & 12 == 12 and dn_classes[95] & 12 == 12)
    assert(dn_classes[130] & 32 == 32 and dn_classes[130] & 2 == 0)
    loop c in dn_classes: print(int(c))
    loop token in dn_symbols: print(int(token))
    # A complete rebuild must detach old readers' snapshots of both arrays.
    old_classes = dn_classes
    old_symbols = dn_symbols
    dn_classes[0] = 255
    dn_symbols[0] = .kw_spawn
    dn_init_symbols()
    assert(old_classes[0] == 0 and old_symbols[0] == .none)
    assert(dn_classes == old_classes and dn_symbols == old_symbols)
    assert(dn_symbols[40 * 128] == .lparen)
    assert(dn_symbols[61 * 128 + 62] == .function)
    assert(dn_symbols[60 * 128 + 60] == .none, "three-byte <<= needs the full scanner")
    assert(dn_symbols[46 * 128 + 46] == .none, "range prefix also starts ellipsis")
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_frontend_symbols_twins(compiler, tmp_path, release):
    out = compare_narrow(compiler, tmp_path, release, ('dewy_tokens', 'frontend_symbols'), DRIVER,
                         doubles={'services.jo': SERVICES}, snapshot=False,
                         services=('dewy_fast', 'lex', 'dewy_fast_lex', 'util', 'diagnostic_exit'))
    assert out.endswith(b'ok\n') and len(out.splitlines()) == 256 + 16384 + 1
