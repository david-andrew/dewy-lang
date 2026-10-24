"""Panic backtraces show the program's functions, not compiler-made helpers."""
import subprocess

from tests.support import compiler  # noqa: F401

# (programs that keep runtime checks for their unproven obligations)
RUNTIME_CHECKS = '\n$runtime_checks\n'


def test_int_main_backtrace_hides_entry_helper(compiler, tmp_path):
    source = tmp_path / 'bt.dewy'
    source.write_text(('main=():>void=>{\n    let xs=[1 2]\n    printl(xs[..5))\n}\n') + RUNTIME_CHECKS)
    binary = tmp_path / 'bt'
    built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=30)
    assert ran.returncode == 101
    assert '    in main (bt.dewy:3)' in ran.stderr
    assert 'h_' not in ran.stderr, ran.stderr
