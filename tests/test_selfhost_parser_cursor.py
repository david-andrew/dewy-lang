"""The hot token cursor preserves EOF, spacing, cache and assignment behavior."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401


DRIVER = r'''use 'main.jo'
use 'parser_cursor.dewy'
use 'parse.jo'
use 'lex.jo'
use 'checker_tokens.dewy'
main = ():
    init_keywords()
    tokens = [Token(kind=.ident, start=0, len=1, pos=11), Token(kind=.assign, start=1, len=1, pos=12), Token(kind=.newline, pos=13), Token(kind=.newline, pos=14), Token(kind=.eof, pos=15)]
    p_toks = data(tokens); p_ntoks = tokens.len(); ti = 0
    print("peek:{pk() == .ident}:{pkn(1) == .assign}:{pkn(100) == .eof}:{cur_pos()}")
    print("reject:{accept(.newline)}:{ti}")
    print("take:{advance()}:{ti}:{accept(.assign)}:{ti}")
    skip_newlines()
    print("eof:{ti}:{pk() == .eof}:{advance()}:{ti}:{accept(.eof)}:{ti}")
    ti = 0
    print("assign:{word_assign_ahead()}:{is_assign_op(.kw_and)}:{is_assign_op(.kw_or)}:{is_assign_op(.kw_xor)}:{is_assign_op(.assign)}:{is_assign_op(.plus)}")
    direct = 0; spaced = 0; soft = 0; keyword_count = 0
    loop i in [0..int(Tok.lazy) + 1):
        k = i as Tok
        if is_assign_op(k): direct += 1
        if is_soft_kw(k): soft += 1
        if is_keyword_tok(k): keyword_count += 1
        print("kind:{i}:{is_keyword_tok(k)}:{is_soft_kw(k)}:{is_assign_op(k)}")
    p_toks[1].start = 2
    loop i in [0..int(Tok.lazy) + 1):
        if is_assign_op(i as Tok): spaced += 1
    print("spaced:{word_assign_ahead()}:{direct}:{spaced}:{soft}:{keyword_count > 0}")
    tokens = [Token(kind=.ident, start=0, len=1), Token(kind=.str_lit, start=2, len=1), Token(kind=.ident, start=4, len=1), Token(kind=.ident, start=6, len=1), Token(kind=.eof, start=7)]
    p_toks = data(tokens); p_ntoks = tokens.len()
    print("space:{space_before(0)}:{space_before(1)}:{space_before(2)}:{space_before(3)}:{space_before(4)}")
    tokens = [Token(kind=.lparen), Token(kind=.lbrack), Token(kind=.ident), Token(kind=.rbrack), Token(kind=.rparen), Token(kind=.eof)]
    p_toks = data(tokens); p_ntoks = tokens.len()
    print("nested:{partner(0)}:{p_toks[0].ival}:{partner(1)}:{p_toks[1].ival}")
    loop c in [94, 42, 47, 37, 43, 45, 38]:
        p_toks[2].ival = c
        print("dot:{c}:{dotop_prec(2)}")
    p_toks[0].ival = 3
    print("cached:{partner(0)}")
    p_toks[0].ival = 0; p_toks[4].kind = .ident
    print("unclosed:{partner(0)}:{p_toks[0].ival}")
'''


def test_parser_cursor_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_cursor',))
    outputs = [subprocess.run([binary], capture_output=True, timeout=60)
               for binary in binaries]
    assert all(result.returncode == 0 for result in outputs), [
        (result.returncode, result.stderr) for result in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    for expected in (
        b'peek:true:true:true:11', b'reject:false:0', b'take:0:1:true:2',
        b'eof:4:true:4:4:true:4', b'assign:true:true:true:true:true:false',
        b'spaced:false:14:11:4:true', b'space:true:false:false:true:false',
        b'nested:4:4:3:3', b'cached:3', b'unclosed:6:6',
        b'dot:94:11', b'dot:42:10', b'dot:47:10', b'dot:37:10',
        b'dot:43:9', b'dot:45:9', b'dot:38:2',
    ):
        assert expected in outputs[0].stdout
