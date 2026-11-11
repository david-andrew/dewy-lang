"""Legacy lexer unit aliases, scaled tokens and invalid suffix diagnostics agree with the frozen Jo leaf."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_diagnostic_double import diagnostic_status
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'lexer_units.dewy'
use 'lex.jo'
use 'source_types.dewy'
use 'checker_tokens.dewy'
use 'util.jo'
main = ():
    loop name in ["s", "sec", "second", "seconds", "ms", "millisecond", "milliseconds", "us", "microsecond", "microseconds", "ns", "nanosecond", "nanoseconds", "min", "minute", "minutes", "h", "hour", "hours", "m", "meter", "meters", "metre", "metres", "cm", "centimeter", "centimeters", "mm", "millimeter", "millimeters", "km", "kilometer", "kilometers", "kg", "kilogram", "kilograms", "g", "gram", "grams", "rad", "radian", "radians", "deg", "degree", "degrees", "turn", "turns", "N", "newton", "newtons", "unknown"]:
        print("unit:{name}:{unit_scale(name)}")
    text = "500ms 2s 90deg\n"
    if args()[1] == "bad": text = "2bogus\n"
    files = [SrcFile(path="case.jo", src=text)]
    tokens = lex(0, text)
    n = 0
    loop token in tokens:
        if token.kind == .float_lit:
            n += 1
            print("literal:{token.fval}:{int(token.flags) & INTF_UNIT != 0}")
    print("literals:{n}")
'''


def test_lexer_units_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    original = selfhost_lsp_double.modules_for

    def modules_for(*args, **kwargs):
        modules = dict(original(*args, **kwargs))
        diagnostic_status(modules)
        return modules

    monkeypatch.setattr(selfhost_lsp_double, 'modules_for', modules_for)
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('lexer_units',))
    for op, code, expected in [('units', 0, b'literals:3'),
                               ('bad', 41, b"unknown unit 'bogus'")]:
        outputs = [subprocess.run([b, op], capture_output=True, timeout=60) for b in binaries]
        assert all(r.returncode == code for r in outputs), [(r.returncode, r.stderr) for r in outputs]
        assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
        assert expected in outputs[0].stdout
        if op == 'units':
            assert b'unit:unknown:0' in outputs[0].stdout
            assert b'literal:0.5:true' in outputs[0].stdout
            assert b'literal:2.0:true' in outputs[0].stdout
