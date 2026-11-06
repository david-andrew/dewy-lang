"""A program function named as a library method, with the same kind of first argument, warns
naming both; which one wins does not change."""
import subprocess

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, text):  # noqa: F811
    source = tmp_path / 'main.dewy'
    source.write_text(text)
    result = subprocess.run([compiler, 'run', source], capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout, [line for line in result.stderr.splitlines() if 'hides the library' in line]


def test_string_method_hidden(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'upper = (s:string):>string => "<{s}>"\nshout = (s:string):>string => s.upper\nmain = () => printl(shout("hi"))\n')
    assert out == '<hi>\n'
    assert len(found) == 1 and ':1:' in found[0]
    assert "'upper' hides the library's method `string.upper`" in found[0]


def test_builtin_array_method_hidden(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'pop = (xs:array<int>):>int => xs.length\nmain = () => printl(pop([1 2]))\n')
    assert out == '2\n'
    assert len(found) == 1 and '`array<int>.pop`' in found[0]


def test_other_first_argument_is_quiet(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'upper = (n:int):>int => n + 1\nmain = () => { printl(upper(1)); printl("a".upper) }\n')
    assert out == '2\nA\n'
    assert found == []


def test_own_name_is_quiet(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'shout = (s:string):>string => s.upper\nmain = () => printl(shout("hi"))\n')
    assert out == 'HI\n'
    assert found == []


def test_own_type_method_is_quiet(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'Pt:type = [x:int upper = () => x + 1]\nmain = () => printl(Pt[1].upper)\n')
    assert out == '2\n'
    assert found == []


def test_game_function_is_quiet(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'scale = (a:float64 b:float64):>float64 => a*b\nmain = () => printl(scale(2.0 3.0))\n')
    assert out == '6.0\n'
    assert found == []


def test_converting_argument_is_quiet(compiler, tmp_path):  # noqa: F811
    out, found = run(compiler, tmp_path, 'sqrt = (n:int):>int => n\nmain = () => printl(sqrt(4))\n')
    assert out == '4\n'
    assert found == []
