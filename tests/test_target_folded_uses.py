"""A name used only in an arm a `$target` or `$build` test leaves out is not unused."""
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''$build.mode = 'MODE'
describe = (verbose:bool count:int):>string => {
    if $build.mode =? 'debug' {
        if verbose return "debug, {count} items"
        return "debug"
    }
    "release"
}
unused = (spare:int):>int => 1
main = () => printl"{describe(true 3)} {unused(2)}"
'''


def test_folded_arm_uses(compiler, tmp_path):  # noqa: F811
    for mode in ('release', 'debug'):
        source = tmp_path / f'{mode}.dewy'
        source.write_text(SOURCE.replace('MODE', mode))
        checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True,
                                 timeout=30, check=False)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "'verbose'" not in checked.stderr and "'count'" not in checked.stderr, checked.stderr
        assert "'spare' is given a value here but never used" in checked.stderr, checked.stderr
