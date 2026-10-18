"""Run project tests with the standalone compiler, including failed-test isolation."""
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope='module')
def compiler():
    path = os.environ.get('DEWY_CORE_COMPILER')
    if not path:
        pytest.skip('set DEWY_CORE_COMPILER for native test runner checks')
    return Path(path).resolve(strict=True)


def command(compiler, *arguments):
    return subprocess.run([compiler, *arguments], capture_output=True, text=True,
                          timeout=30, check=False)


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.core_quick
def test_core_native_tests(compiler, tmp_path, flags):
    source = tmp_path / 'tests.dewy'
    source.write_text(r'''let values = [20 22]
add = (a:int64 b:int64) => a+b
main = () => panic("test must not run main")
test "adds numbers" { assert(add(values[0] values[1]) =? 42) }
test "mutates its own copy" { values[0] = 0 assert(values[0] =? 0) }
test "starts with fresh globals" { assert(values[0] =? 20) }
test "\"quoted\" 🙂" { assert(true) }
''')
    result = command(compiler, 'test', *flags, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '4 tests passed' in result.stdout
    assert 'test "quoted" 🙂 ... ok' in result.stdout
    filtered = command(compiler, 'test', *flags, source, 'adds', 'fresh')
    assert filtered.returncode == 0, filtered.stdout + filtered.stderr
    assert '2 tests passed (2 not run' in filtered.stdout
    assert 'mutates' not in filtered.stdout
    missing = command(compiler, 'test', *flags, source, 'no-such-name')
    assert missing.returncode != 0
    assert 'no test\'s name' in missing.stderr


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize('failure', ['assert(false)', 'panic("intentional")', 'exit(7)'])
def test_core_native_test_failure_isolation(compiler, tmp_path, flags, failure):
    source = tmp_path / 'tests.dewy'
    source.write_text(f'''test "before" {{ assert(true) }}
test "fails" {{ {failure} }}
test "after" {{ assert(true) }}
''')
    result = command(compiler, 'test', *flags, source)
    assert result.returncode != 0
    assert 'test before ... ok' in result.stdout
    assert 'test after ... ok' in result.stdout
    assert '2 passed, 1 failed' in result.stdout


def test_core_native_tests_check_and_build(compiler, tmp_path):
    source = tmp_path / 'program.dewy'
    source.write_text('test "checked only" { assert(missing_test_value) }\nmain=()=>42')
    result = command(compiler, 'check', source)
    assert result.returncode != 0 and 'missing_test_value' in result.stderr
    result = command(compiler, source)
    assert result.returncode == 42, result.stdout + result.stderr


@pytest.mark.parametrize('tests', ['', 'test "also checked" { assert(true) }\n'])
@pytest.mark.parametrize(('main', 'error'), [
    ('main=()=>missing_main_value', 'missing_main_value'),
    ('main=()=>[1 2]', 'main must return'),
    ('helper=()=>missing_helper_value\nmain=()=>helper()', 'missing_helper_value'),
])
def test_core_check_main_with_tests(compiler, tmp_path, tests, main, error):
    source = tmp_path / 'program.dewy'
    source.write_text(tests + main)
    result = command(compiler, 'check', source)
    assert result.returncode != 0 and error in result.stderr, result.stdout + result.stderr


def test_core_check_does_not_execute_main(compiler, tmp_path):
    source = tmp_path / 'program.dewy'
    source.write_text('main=()=>panic("must only check")')
    result = command(compiler, 'check', source)
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_native_tests_imports(compiler, tmp_path):
    (tmp_path / 'helper.dewy').write_text('answer=()=>42\ntest "helper only" { assert(false) }')
    source = tmp_path / 'tests.dewy'
    source.write_text('from p"helper.dewy" import answer\ntest "main file" { assert(answer() =? 42) }')
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 test passed' in result.stdout and 'helper only' not in result.stdout


@pytest.mark.parametrize(('text', 'error'), [
    ('main=()=>0', 'no tests'),
    ('test_add=()=>true', 'is a function, not a test'),
    ('test "interpolated {1}" {}', 'constant string'),
    ('test "missing block"', "expected '{'"),
    ('main=()=>{ test "nested" {} }', 'top level'),
    ('test "no early exit" { return }', 'outside of a function'),
])
def test_core_native_tests_diagnostics(compiler, tmp_path, text, error):
    source = tmp_path / 'tests.dewy'
    source.write_text(text)
    result = command(compiler, 'test', source)
    assert result.returncode != 0
    assert error in result.stderr, result.stdout + result.stderr


def test_core_native_tests_contextual_keyword(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('test=(x:str)=>x.length\ntest "ordinary name" { assert(test("abc") =? 3) test"abcd"; }')
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_native_tests_format(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('test "formatted"{\nassert(20+22 =? 42)\n}\n')
    result = command(compiler, 'fmt', source)
    assert result.returncode == 0, result.stderr
    assert '    assert(' in source.read_text()
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert command(compiler, 'fmt', '--check', source).returncode == 0


def test_core_native_tests_help(compiler):
    result = command(compiler, 'test', '--help')
    assert result.returncode == 0
    assert 'test [--watch] [--release] file.dewy [name filters...]' in result.stderr


def test_core_native_tests_game(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    source.write_text('''window("headless tests" 320 240)
update=(dt:float64):>void=>panic("must not update")
draw=():>void=>panic("must not draw")
test "game logic" { assert(20+22 =? 42) }
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': ''}
    result = subprocess.run([compiler, 'test', source], env=env, capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 test passed' in result.stdout


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize(('name', 'count'), [('paddle_tests', 3), ('trajectory_fit', 2), ('reaction_model', 2)])
def test_core_native_tests_example(compiler, flags, name, count):
    source = Path(__file__).resolve().parents[2] / f'examples/sloppy_core/{name}.dewy'
    result = command(compiler, 'test', *flags, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'{count} tests passed' in result.stdout
