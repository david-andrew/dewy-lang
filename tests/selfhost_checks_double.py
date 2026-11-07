"""One compiler pair per process: every moved expression and checking leaf against its frozen twin, on real services.

The leaves call the checker and one another freely, so a double for each would hide what they do.
Each test file names the programs reaching its group; programs vary at runtime, so a new program
never costs a compiler build. Output images, diagnostics and statuses must match.
"""
import subprocess

from tests.support import ROOT
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

LEAVES = tuple(sorted(p.stem for p in (ROOT / 'compiler').glob('checks_*.dewy')))
DRIVER = '''use 'main.jo'
main = ():
    lower_test_cli()
    print(read_file(args()[4]) ?? "")
'''


def compare_checks(compiler, tmp_path, monkeypatch, cases, flags=()):
    """Compile each program through both builds; return (compiled, rejected) counts."""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    output = tmp_path / 'program'
    compiled = rejected = 0
    for case in cases:
        source = ROOT / case if case.startswith('tests/') else ROOT / 'tests/cases' / (case + '.dewy')
        expected = subprocess.run([compiler, 'build', source, '-o', output, *flags],
                                  capture_output=True, timeout=60)
        modules = modules_for(source, output, LEAVES, flags)
        modules.with_stderr = True
        compare_leaf(compiler, tmp_path, False, DRIVER, status=expected.returncode,
                     extra_stems=LEAVES, jo_doubles=modules)
        compiled += expected.returncode == 0
        rejected += expected.returncode != 0
    return compiled, rejected
