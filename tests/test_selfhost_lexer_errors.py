"""Lexer token diagnostics, mixed indentation and encoded error positions agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'lexer_errors.dewy'
use 'lex.jo'
use 'checker_tokens.dewy'
main = ():
    loop i in [0..int(Tok.lazy)):
        print("token:{i}:{tok_name(i as Tok)}:{tok_text_at(i)}")
    print("braces:{tok_name(.lbrace)}:{tok_name(.rbrace)}:plus:{tok_text_at(int(Tok.plus))}")
    loop tab in [false, true]:
        loop space in [false, true]:
            lx_tab_indent = tab; lx_space_indent = space
            print("indent:{tab}:{space}:{mixed_indent_note()}")
    if args()[1] == "error":
        lx_file = 3; lx_base = 37
        lx_err(5, "lexer error")
'''


def test_lexer_errors_match_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        modules['diagnostic_exit.dewy'] = modules['diagnostic_exit.dewy'].replace(
            'printl(msg); exit(41)', 'printl("{_p}:{msg}"); exit(41)')
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_errors',))
    for op, code, expected in [('names', 0, b"braces:'{':'}':plus:+"),
                               ('error', 41, b'3298534883370:lexer error')]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        assert outputs[0].stdout.count(b'the file indents some lines') == 1
        assert b'indent:false:false:\n' in outputs[0].stdout
