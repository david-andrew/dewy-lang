"""Replacing and clearing borrowed parse-unit tokens matches the frozen lifetime twin."""
import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = '''use 'checker_tokens.dewy'
use 'parser_lifetime.dewy'
struct Token:
    kind: Tok
    flags: i32
    pos: int
    start: i32
    len: i32
    ival: int
    fval: f64
toks: Token[]
p_toks: *Token
p_ntoks = 0
lifetime_bound = parser_lifetime_bind(&toks as *int)
lex = (file: int, src: str, from: int = 0, to: int = -1) -> Token[]:
    stop = if to < 0: len(src) else: to
    out: Token[]
    loop i in [from..stop): out.push(Token(kind=.int_lit, pos=(file << 40) + i, ival=int(src[i])))
    out.push(Token(kind=.eof))
    out
'''
DRIVER = '''main = ():
    p_clear_unit(); assert(p_ntoks == 0 and p_toks == null)
    p_lex_unit(2, "abcd")
    assert(p_ntoks == 5 and p_toks[0].ival == 97 and p_toks[3].pos == (2 << 40) + 3)
    saved = toks
    p_lex_unit(3, "012345", 2, 4)
    assert(p_ntoks == 3 and p_toks[0].ival == 50 and p_toks[1].ival == 51 and p_toks[2].kind == .eof)
    assert(saved.len() == 5 and saved[0].ival == 97)
    p_clear_unit(); assert(p_ntoks == 0 and toks.len() == 0 and saved.len() == 5)
    p_lex_unit(0, "")
    assert(p_ntoks == 1 and p_toks[0].kind == .eof)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_parser_lifetime_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('checker_tokens', 'parser_lifetime'), DRIVER,
                          doubles={'services.jo': SERVICES}, services=('parse', 'lex')) == b'ok\n'
