"""Lifecycle lowering emits the twin's bytes across recursive and task owners."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_ownership_lower_twins(compiler, tmp_path, monkeypatch):
    # Hook helpers need the real instantiator, layouts and runtime functions.
    # One cached default-mode driver pair covers all programs and both flags.
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
main = ():
    lower_test_cli()
    print(read_file(args()[4]) ?? "")
'''
    for case, status in [
        ('ownership/recursive_owner_copy', 0),
        ('ownership/inherited_hooks', 0),
        ('ownership/partial_field_paths', 0),
        ('ownership/hook_result_adoption', 0),
        ('ownership/growable_dictionary_moves', 0),
        ('task_capture_panic/owner_task_panic_inline', 101),
    ]:
        source = ROOT / 'tests/cases' / (case + '.dewy')
        for release in (False, True):
            output = tmp_path / 'program'
            modules = modules_for(source, output, 'ownership_lower',
                                  flags=('--release',) if release else ())
            image = compare_leaf(compiler, tmp_path, False, driver,
                                 extra_stems=('ownership_lower',), jo_doubles=modules)
            assert image == output.read_bytes() + b'\n', (case, release)
            ran = subprocess.run([output], capture_output=True, timeout=30)
            assert ran.returncode == status, (case, release, ran.stderr)
            assert ran.stdout == source.with_suffix('.out').read_bytes(), (case, release)
