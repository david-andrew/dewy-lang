"""`p.modified` is the `Instant` the file last changed, to the nanosecond (design D10), not
a civil `Date`; a missing file is `FileNotFound`."""
import os
import subprocess

from tests.support import compiler  # noqa: F401

SOURCE = '''main = ():>void => {
    let t = p"stamped.txt".modified
    printl(t is? Instant)
    printl(t =? instant"2023-11-14T22:13:20.123456789Z")
    printl(p"absent.txt".modified is? FileNotFound)
}
'''


def test_modified_is_an_instant_with_the_files_nanoseconds(compiler, tmp_path):  # noqa: F811
    stamped = tmp_path / 'stamped.txt'
    stamped.write_text('x')
    os.utime(stamped, ns=(1_700_000_000_000_000_000, 1_700_000_000_123_456_789))
    (tmp_path / 'main.dewy').write_text(SOURCE)
    ran = subprocess.run([compiler, 'run', 'main.dewy'], text=True, capture_output=True, timeout=120, cwd=tmp_path)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.splitlines() == ['true', 'true', 'true'], ran.stdout + ran.stderr
