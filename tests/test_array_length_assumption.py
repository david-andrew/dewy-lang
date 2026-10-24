"""The array-size convenience bound has the same scoped opt-out as progress."""
import re
import subprocess

from tests.support import compiler


def test_array_length_bound_optout(compiler, tmp_path):
    body = '''f=(xs:array<int64>):>int64=>xs.length*256
main=()=>printl(f([1 2 3]))
'''
    for disabled in [False, True]:
        source = tmp_path / 'length.dewy'
        source.write_text((('$no_assumed_bounds\n' if disabled else '') + body) + "\n$runtime_checks\n")
        binary = tmp_path / 'length'
        built = subprocess.run([compiler, 'build', source, '--ir', '-o', binary], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        function = next(b for b in re.split(r'^fn ', built.stdout, flags=re.MULTILINE) if b.startswith('f_f_'))
        assert ('checked_mul' in function) == disabled, function
        ran = subprocess.run([binary], capture_output=True, text=True)
        assert ran.returncode == 0 and ran.stdout.strip() == '768'
