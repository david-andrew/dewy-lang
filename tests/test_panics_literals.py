"""A literal argument can rule out a library call's one failure: a range
without a step, a power with a literal exponent >= 0, a rational with a
literal nonzero denominator. Without it the call may panic."""
import subprocess

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source, *arguments):
    path = tmp_path / 'program.dewy'
    path.write_text('$runtime_checks=false\n' + source)
    return subprocess.run([compiler, *arguments, path.name], text=True, capture_output=True, timeout=60, cwd=tmp_path)


def test_literals_rule_out_failures(compiler, tmp_path):
    source = 'main=():>void=>{\n    let w=[0..10)\n    let s=[0,2..10]\n    let big=2^100\n    let r=rational(1 3)\n    printl"{3 in? w} {4 in? s} {big % 7} {r =? rational(2 6)}"\n}\n'
    result = run(compiler, tmp_path, source, 'run')
    assert result.returncode == 0 and result.stdout == 'true true 2 true\n', result.stdout + result.stderr


def test_unknown_exponent_may_panic(compiler, tmp_path):
    result = run(compiler, tmp_path, 'f=(n:int64):>int=>2^n\nmain=():>void=>printl(f(3))\n', 'check')
    assert result.returncode != 0 and 'calling `power` may panic' in result.stderr, result.stderr
