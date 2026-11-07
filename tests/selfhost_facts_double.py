"""One compiler pair per process: every moved facts leaf against its frozen twin, on real services.

The facts leaves call one another and the evaluator freely, so a double for each would hide what
they do. Every test file names the programs reaching its group; programs vary at runtime, so a
new program never costs a compiler build. Output images, diagnostics and statuses must match.
"""
import subprocess

from tests.support import ROOT
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for

LEAVES = tuple(sorted(p.stem for p in (ROOT / 'compiler').glob('facts_*.dewy')))
MOVED = ('error_ops', 'dewy_method_ops', 'decimal_ops', 'copy_ops', 'partition_ops', 'inline_ops', 'proof_ops', 'witness_ops', 'directive_ops', 'float_ops', 'unit_ops', 'reader_service_ops', 'spirv_ops', 'type_ops', 'dewy_node_ops', 'glsl_ops', 'msl_ops')
DRIVER = '''use 'main.jo'
main = ():
    lower_test_cli()
    print(read_file(args()[4]) ?? "")
'''


def compare_facts(compiler, tmp_path, monkeypatch, cases, flags=(), leaves=LEAVES):
    """Compile each program (a tests/cases name or a repository path) through both builds; return how many compiled."""
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    output = tmp_path / 'program'
    compiled = 0
    for case in cases:
        source = ROOT / case if case.startswith(('tests/', 'bench/')) else ROOT / 'tests/cases' / (case + '.dewy')
        expected = subprocess.run([compiler, 'build', source, '-o', output, *flags],
                                  capture_output=True, timeout=60)
        modules = modules_for(source, output, leaves, flags)
        modules.with_stderr = True
        compare_leaf(compiler, tmp_path, False, DRIVER, status=expected.returncode,
                     extra_stems=leaves, jo_doubles=modules)
        compiled += expected.returncode == 0
    return compiled


def compare_moved(compiler, tmp_path, monkeypatch, cases, flags=()):
    """The same, one compiler pair over the leaves that are not facts leaves but need real services."""
    return compare_facts(compiler, tmp_path, monkeypatch, cases, flags, MOVED)
