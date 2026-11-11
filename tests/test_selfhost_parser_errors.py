"""Parser keyword and empty-block diagnostics agree with the frozen Jo leaf. agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'parser_errors.dewy'
use 'parse.jo'
use 'lex.jo'
use 'checker_tokens.dewy'
main = ():
    tokens = [Token(kind=.dot, pos=7), Token(kind=.kw_build, pos=9), Token(kind=.ident, pos=11)]
    op = args()[1]
    if op == "empty":
        tokens[0].kind = .colon
        p_toks = data(tokens); p_ntoks = tokens.len(); ti = 3
        parse_empty_block()
    if op == "when": tokens[1].kind = .kw_when
    if op == "match": tokens[1].kind = .kw_match
    if op == "use": tokens[1].kind = .kw_use
    if op == "paren": tokens[1].kind = .lparen
    p_toks = data(tokens); p_ntoks = tokens.len()
    keyword_name_error(1)
'''


def test_parser_errors_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('parser_errors',))
    for op, expected in [('build', b'it starts a build block'),
                         ('when', b'it chooses code by the target'),
                         ('match', b'for a regular expression'),
                         ('use', b"it brings in a file's names"),
                         ('paren', b"'(' is a keyword"),
                         ('empty', b'nothing is under this line')]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == 41 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
