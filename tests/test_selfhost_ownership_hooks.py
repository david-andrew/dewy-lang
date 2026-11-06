"""Hook discovery, inheritance, no-failure summaries and rejection match Jo."""
import re
import subprocess

from tests.support import ROOT, compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.selfhost_lower_double import modules_for


def test_ownership_hooks_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
main = ():
    lower_test_cli()
    print(read_file(args()[4]) ?? "")
'''
    # All runtime cases share the same graph, fatal service and driver pair.
    for case, message in [
        ('ownership/inherited_hooks', None),
        ('ownership/growable_dictionary_keys', None),
        ('ownership/composed_hooks', None),
        ('ownership/spawn_owner_capture', None),
        ('ownership/scalar_hook_duplicate', b'duplicate $__drop__ hook'),
        ('ownership/copy_hook_failure', b'proven no-failure summary'),
        ('ownership/copy_hook_write', b'readonly receiver'),
        ('ownership/scalar_return_hook', b'must return void'),
    ]:
        source = ROOT / 'tests/cases' / (case + '.dewy')
        for release in ((False, True) if message is None else (False,)):
            output = tmp_path / 'program'
            modules = modules_for(source, output, 'ownership_hooks',
                                  flags=('--release',) if release else ())
            modules['util.jo'], count = re.subn(
                r'(?m)^fatal = \(p0: int, msg0: str\):\n(?:[ \t].*\n|\n)*',
                'fatal = (p0: int, msg0: str):\n    print(msg0)\n    exit(41)\n\n',
                modules['util.jo'], count=1)
            assert count == 1
            result = compare_leaf(compiler, tmp_path, False, driver,
                                  status=41 if message else 0,
                                  extra_stems=('ownership_hooks',), jo_doubles=modules)
            if message:
                assert message in result, (case, result)
            else:
                assert result == output.read_bytes() + b'\n', (case, release)
                ran = subprocess.run([output], capture_output=True, timeout=30)
                assert ran.returncode == 0, (case, release, ran.stderr)
                assert ran.stdout == source.with_suffix('.out').read_bytes(), (case, release)
