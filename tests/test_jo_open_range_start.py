import subprocess

from tests.support import compiler  # noqa: F401


def test_jo_range_with_open_start_skips_its_start(compiler, tmp_path):
    # `(0..3]` leaves out 0: the Jo reader rewrites the start as `0 + 1`.
    (tmp_path / 'ranges.jo').write_text('total = () -> int:\n'
                                        '    s = 0\n'
                                        '    loop i in (0..3]:\n'
                                        '        s = s * 10 + i\n'
                                        '    return s\n')
    path = tmp_path / 'user.dewy'
    path.write_text('from p"ranges.jo" import total\nmain=()=>printl(total())\n')
    binary = tmp_path / 'user'
    built = subprocess.run([compiler, 'build', path, '-o', binary], text=True, capture_output=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], text=True, capture_output=True, timeout=30)
    assert ran.stdout == '123\n', ran.stdout + ran.stderr
