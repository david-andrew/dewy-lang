"""Run project tests with the standalone compiler, including failed-test isolation."""
import json
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


def shown(path):
    """A path as the compiler prints it: / separators, and on Windows a lower-case drive."""
    text = str(path).replace('\\', '/')
    return text[0].lower() + text[1:] if os.name == 'nt' and text[1:2] == ':' else text


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.core_quick
def test_core_native_tests(compiler, tmp_path, flags):
    source = tmp_path / 'tests.dewy'
    source.write_text(r'''let values = [20 22]
add = (a:int64 b:int64) => a+b
main = () => panic("test must not run main")
$test
adds_numbers = () => $expect add(values[0] values[1]) =? 42
$test
mutates_its_own_copy = () => {
    values[0] = 0
    $expect values[0] =? 0
}
$test
starts_with_fresh_globals = () => $expect values[0] =? 20
$test(cases=(1 2 -3))
negates = (x:int64) => $expect 0 - (0 - x) =? x
''')
    result = command(compiler, 'test', *flags, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '......\n6 passed\n'
    filtered = command(compiler, 'test', *flags, source, 'adds', 'fresh')
    assert filtered.returncode == 0, filtered.stdout + filtered.stderr
    assert filtered.stdout == '..\n2 passed (4 not run: their names do not match)\n'
    missing = command(compiler, 'test', *flags, source, 'no-such-name')
    assert missing.returncode != 0
    assert 'no test\'s name' in missing.stderr


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize(('failure', 'status'), [
    ('$expect false', 1), ('$fail "deliberate"', 1), ('panic("intentional")', 101),
    ('$runtime_assert args().length =? 99', 101), ('exit(0)', 101), ('exit(7)', 101)])
def test_core_native_test_failure_isolation(compiler, tmp_path, flags, failure, status):
    source = tmp_path / 'tests.dewy'
    source.write_text(f'''$test
before = () => $expect true
$test
fails = () => {{
    printl("shown on failure")
    {failure}
}}
$test
after = () => $expect true
''')
    result = command(compiler, 'test', *flags, source)
    assert result.returncode == status, result.stdout + result.stderr
    assert result.stdout.startswith('.F.\n--- FAIL fails\nshown on failure\n'), result.stdout
    assert result.stdout.endswith('1 failed, 2 passed\n' if status == 1 else '1 failed, 2 passed (1 aborted)\n')


def test_core_native_test_expectations(compiler, tmp_path):
    """A failed expectation returns from its function; a helper's failure fails the test that called it."""
    source = tmp_path / 'tests.dewy'
    source.write_text('''first = (xs:array<int64>):>void => {
    $expect xs.length >? 0, "nonempty input"
    printl("helper continued")
}
$test
helper_fails = () => {
    let empty:array<int64> = []
    first(empty)
    printl("test continued")
}
$test
narrows = () => {
    let value:int64? = 7
    $expect value is? int64
    $expect value + 1 =? 8, "value is {value}"
    printl("not shown")
}
$test(cases=[[a=1 b=2] [a=(-3) b=4]])
pairs = (a:int64 b:int64) => $expect a - b <? 0, "{a} is not below {b}"
main=():>void=>exit(0)
''')
    result = command(compiler, 'test', '--json', source)
    assert result.returncode == 1, result.stdout + result.stderr
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert [(line['test'], line['status']) for line in lines[:-1]] == [
        ('helper_fails', 'fail'), ('narrows', 'pass'), ('pairs[0]', 'pass'), ('pairs[1]', 'pass')]
    failed = lines[0]
    assert failed['stdout'] == 'test continued\n'
    assert failed['output'].splitlines() == [
        f'{shown(source)}:2:5: expectation failed: nonempty input',
        '        $expect xs.length >? 0, "nonempty input"',
        '                ^~~~~~~~~~~~~~',
        'note: xs.length is 0',
        'test continued']
    assert lines[-1] == {'passed': 3, 'failed': 1, 'aborted': 0, 'not_run': 0, 'exit': 1}
    # An ordinary run is unaffected by the tests, which still check and build.
    result = command(compiler, source)
    assert result.returncode == 0 and result.stdout == '' and result.stderr == '', result.stderr


def test_core_native_test_computed_cases(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('''let CASES:array<int64> = [2 4 7 8]
$test(cases=CASES)
even = (x:int64) => $expect x % 2 =? 0, "{x} is odd"
''')
    result = command(compiler, 'test', source)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.startswith('..F.\n--- FAIL even[2]\n')
    assert 'expectation failed: 7 is odd' in result.stdout
    assert result.stdout.endswith('1 failed, 3 passed\n')


def test_core_native_test_refuted_expectation(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('$test\nrefuted = () => $expect 1 =? 2\n$test\nliteral = () => $expect false\n')
    result = command(compiler, 'test', source)
    assert result.returncode == 2, result.stdout + result.stderr
    assert result.stderr.count('warning: this expectation always fails') == 1


@pytest.mark.parametrize('flags', [[], ['--release']])
def test_core_native_test_child_selection(compiler, tmp_path, flags):
    """Exercise the re-execution protocol locally as well as on Windows hosts."""
    source = tmp_path / 'child.dewy'
    helper = tmp_path / 'helper.dewy'
    helper.write_text('let original_args=args()\n')
    source.write_text('''from p"helper.dewy" import original_args
let values=[20 22]
$test
first = () => {
    values[0]=0
    panic("wrong test selected")
}
$test
chosen = () => {
    $expect values[0] =? 20
    let arguments=args()
    $expect arguments.length =? 2
    $expect arguments[0] =? "original program name"
    $expect arguments[1] =? "original filter"
    $expect original_args =? arguments
    printl"child ran"
}
$test
last = () => panic("child continued after its test")
''')
    result = command(compiler, 'test', *flags, source, '--dewy-internal-test', '2',
                     'original program name', 'original filter')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'child ran\n'
    missing = command(compiler, 'test', *flags, source, '--dewy-internal-test', '9',
                      'original program name')
    assert missing.returncode != 0
    assert 'selected test was not reached' in missing.stderr


def test_core_native_tests_check_and_build(compiler, tmp_path):
    source = tmp_path / 'program.dewy'
    source.write_text('$test\nchecked_only = () => $expect missing_test_value\nmain=():>void=>exit(42)')
    result = command(compiler, 'check', source)
    assert result.returncode != 0 and 'missing_test_value' in result.stderr
    result = command(compiler, 'test', source)
    assert result.returncode == 102 and 'missing_test_value' in result.stderr


@pytest.mark.parametrize('tests', ['', '$test\nalso_checked = () => $expect true\n'])
@pytest.mark.parametrize(('main', 'error'), [
    ('main=():>void=>exit(missing_main_value)', 'missing_main_value'),
    ('main=()=>[1 2]', 'main returns void or the errors'),
    ('helper=()=>missing_helper_value\nmain=():>void=>exit(helper())', 'missing_helper_value'),
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
    (tmp_path / 'helper.dewy').write_text('answer=()=>42\n$test\nhelper_only = () => $expect false\n')
    source = tmp_path / 'tests.dewy'
    source.write_text('from p"helper.dewy" import answer\n$test\nmain_file = () => $expect answer() =? 42\n')
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '.\n1 passed\n'


@pytest.mark.parametrize(('text', 'error'), [
    ('main=()=>0', 'no tests'),
    ('test_add=()=>true', 'is a function, not a test'),
    ('test "old form" { assert(true) }', 'a test is a function marked `$test`'),
    ('$test\nlet x = 5', '`$test` marks a module-level function'),
    ('main=()=>0\n$test', '`$test` marks a module-level function'),
    ('$test\n$test\nf=()=>$expect true', 'a second `$test`'),
    ('$test\nf=(x:int64)=>$expect x =? x', 'give it cases'),
    ('$test(cases=(1 2))\nf=()=>$expect true', 'cannot be given cases'),
    ('$test(case=(1))\nf=(x:int64)=>$expect true', 'takes its cases as'),
    ('$test(cases=())\nf=(x:int64)=>$expect true', 'at least one case'),
    ('$expect true', 'belongs in a function'),
    ('f=(x:int64):>int64=>{ $expect x >? 0\nreturn x }\n$test\nt=()=>$expect f(1) =? 1', 'this function gives a value'),
    ('$test\nf=()=>{ let y = $expect true }', 'is a statement'),
])
def test_core_native_tests_diagnostics(compiler, tmp_path, text, error):
    source = tmp_path / 'tests.dewy'
    source.write_text(text)
    result = command(compiler, 'test', source)
    assert result.returncode == 102
    assert error in result.stderr, result.stdout + result.stderr


def test_core_native_tests_contextual_keyword(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('test=(x:string)=>x.length\n$test\nordinary_name = () => {\n    $expect test("abc") =? 3\n    test"abcd";\n}\n')
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_native_tests_format(compiler, tmp_path):
    source = tmp_path / 'tests.dewy'
    source.write_text('$test\nformatted=()=>{\n$expect 20+22 =? 42\n}\n')
    result = command(compiler, 'fmt', source)
    assert result.returncode == 0, result.stderr
    assert '$test\n' in source.read_text() and '    $expect ' in source.read_text()
    result = command(compiler, 'test', source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert command(compiler, 'fmt', '--check', source).returncode == 0


def test_core_native_tests_help(compiler):
    result = command(compiler, 'test', '--help')
    assert result.returncode == 0
    assert 'test [--watch] [--release] [--json] file.dewy [name filters...]' in result.stderr


def test_core_native_tests_game(compiler, tmp_path):
    source = tmp_path / 'game.dewy'
    (tmp_path / 'setup.dewy').write_text('window("imported setup" 320 240)\nready=()=>true\n')
    source.write_text('''from p"setup.dewy" import ready
window("headless tests" 320 240)
update=(dt:float64):>void=>panic("must not update")
draw=():>void=>panic("must not draw")
$test
game_logic = () => {
    $expect ready()
    $expect 20+22 =? 42
}
''')
    env = {**os.environ, 'DISPLAY': '', 'WAYLAND_DISPLAY': ''}
    result = subprocess.run([compiler, 'test', source], env=env, capture_output=True,
                            text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == '.\n1 passed\n'


@pytest.mark.parametrize('flags', [[], ['--release']])
@pytest.mark.parametrize(('name', 'count'), [('paddle_tests', 3), ('trajectory_fit', 2), ('reaction_model', 2)])
def test_core_native_tests_example(compiler, flags, name, count):
    source = Path(__file__).resolve().parents[1] / f'examples/{name}.dewy'
    result = command(compiler, 'test', *flags, source)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith(f'{count} passed\n')


def test_core_native_tests_directory(compiler, tmp_path):
    """`test directory` runs each file with a `$test` line in its own process and adds up."""
    (tmp_path / 'sub').mkdir()
    (tmp_path / '.hidden').mkdir()
    (tmp_path / 'a.dewy').write_text('$test\nok = () => $expect true\n$test(cases=(1 2))\nc = (x:int64) => $expect x =? 1\n')
    (tmp_path / 'sub' / 'b.dewy').write_text('$test\nb_ok = () => $expect 2 =? 2\n')
    (tmp_path / 'program.dewy').write_text('main=():>void=>exit(0)\n')
    (tmp_path / '.hidden' / 'h.dewy').write_text('$test\nhidden = () => $expect false\n')
    result = subprocess.run([compiler, 'test', '.'], cwd=tmp_path, capture_output=True, text=True,
                            timeout=60, check=False)
    assert result.returncode == 1, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[:3] == ['./a.dewy ..F', './sub/b.dewy .', '--- FAIL ./a.dewy: c[1]']
    assert lines[-1] == '1 failed, 3 passed'
    result = subprocess.run([compiler, 'test', '--json', '.', 'b_'], cwd=tmp_path, capture_output=True,
                            text=True, timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    items = [json.loads(line) for line in result.stdout.splitlines()]
    assert items[0]['test'] == 'b_ok' and items[1]['file'] == './sub/b.dewy'
    assert items[-1] == {'passed': 1, 'failed': 0, 'files': 2, 'exit': 0}
