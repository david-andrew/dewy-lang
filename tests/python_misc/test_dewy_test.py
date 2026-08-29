"""`$expect`, `$test`, test-mode compilation, and `dewy test` (whose runner is written in Dewy)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from dewy.backend.udewy import codegen
from dewy.parser import p0, t1
from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError
from udewy.frontend import EntryPointOptions, entry_point

from test_cleanparse_udewy_e2e import x86_64_toolchain_available

REPO_ROOT = Path(__file__).resolve().parents[2]
needs_toolchain = pytest.mark.skipif(not x86_64_toolchain_available(), reason='needs the x86_64 toolchain')


def _compile(source: str, *, test: bool = False) -> str:
    return codegen(SrcFile(None, source), test=test)


SAMPLE = '''let identity = (x:int64):>int64 => x

$test
let some_test_case = () => {
    $expect identity(42) =? 42, "forty-two isn't itself"
}

$test(cases=(1 2 3 4))
let identity_holds = (x:int64) => $expect identity(x) =? x, "identity of {x} is not {x}. got {identity(x)}"

$test(cases=[
    [a=1 b=2]
    [a=5 b=7]
    [a=(-3) b=4]
])
let commutative = (a:int64 b:int64) => {
    $expect a + b =? b + a
}

$test(cases=(1 2 3))
let fails_on_two = (x:int64) => {
    $expect x not=? 2, "two is not welcome"
    printl"  ({x} is fine)"
}

let main = ():>int64 => {
    printl"main is not the entry in test mode"
    return 7
}
'''


# ------------------------------------------------------------ the directive form

def test_assertion_directives_own_their_comma() -> None:
    """`$assert cond, message` is form grammar: the top-level comma separates the message (`p0.AssertDirective`)."""
    block = p0.parse(SrcFile(None, '$expect x <? 3, "m"\n$assert y =? 1\nlet f = (x:int64) => $expect x =? 1, "one"\n'))
    expect, assertion, declaration = block.inner
    assert isinstance(expect, p0.AssertDirective) and expect.name == 'expect'
    assert isinstance(expect.condition, p0.BinOp) and isinstance(expect.condition.op, t1.Operator) and expect.condition.op.symbol == '<?'
    assert isinstance(expect.message, p0.Atom) and isinstance(expect.message.item, t1.String)
    assert isinstance(assertion, p0.AssertDirective) and assertion.name == 'assert' and assertion.message is None
    # the inline form `=> $expect …` is the function's whole body
    assert isinstance(declaration, p0.KeywordExpr)
    function = declaration.parts[1].right
    assert isinstance(function, p0.BinOp) and isinstance(function.right, p0.AssertDirective)


# ------------------------------------------------------------ `$expect`

def test_expect_belongs_in_void_functions() -> None:
    with pytest.raises(UserError, match='`\\$expect` outside a function'):
        _compile('$expect 1 =? 1\n')
    with pytest.raises(UserError, match='returns a value'):
        _compile('let f = (x:int64):>int64 => { $expect x >? 0  return x }\n')


def test_expect_narrows_and_lowers_to_a_recorded_return() -> None:
    emitted = _compile('let f = (v:int64|string):>void => { $expect v is? int64  let w:int64 = v + 1 }\n')
    assert '_expectation_report(' in emitted and '_expect_failed()' in emitted
    # an expectation the checker decides costs nothing (the prelude still defines `_expect_failed`)
    assert '_expect_failed()' not in _compile('let f = () => { $expect true }\n')


def test_refuted_expectation_warns_but_still_compiles(capsys: pytest.CaptureFixture[str]) -> None:
    emitted = _compile('let f = () => { let x:int64 = 1  $expect x =? 2, "one is two" }\n')
    assert '_expect_failed()' in emitted
    assert 'expectation refuted at compile time' in capsys.readouterr().err
    # a literal `false` is the deliberate "fail here": no warning
    _compile('let f = () => { $expect false, "not reached" }\n')
    assert 'refuted' not in capsys.readouterr().err


# ------------------------------------------------------------ `$test`

def test_test_annotation_forms_are_validated() -> None:
    with pytest.raises(UserError, match='inside a block'):
        _compile('let f = () => {\n    $test\n    let g = () => {}\n}\n')
    with pytest.raises(UserError, match='must mark a function declaration'):
        _compile('$test\nlet x = 5\n')
    with pytest.raises(UserError, match='takes parameters but `\\$test` gives no cases'):
        _compile('$test\nlet t = (x:int64) => $expect x >? 0\n')
    with pytest.raises(UserError, match='takes no parameters, but'):
        _compile('$test(cases=(1 2))\nlet t = () => $expect 1 =? 1\n')
    with pytest.raises(UserError, match='unknown `\\$test` parameter `fixtures`'):
        _compile('$test(fixtures=[db=1])\nlet t = () => $expect 1 =? 1\n')


def test_test_mode_generates_the_runner_and_keeps_main_otherwise() -> None:
    plain = _compile(SAMPLE)
    assert check.TEST_ENTRY_NAME not in plain
    emitted = _compile(SAMPLE, test=True)
    assert check.TEST_ENTRY_NAME in emitted
    # the runner calls each test per case, spliced as written
    assert 'commutative' in emitted and 'identity_holds' in emitted and 'fails_on_two' in emitted


def test_runner_problems_point_at_the_generated_call() -> None:
    with pytest.raises(Exception, match='type mismatch|no valid interpretation') as failure:
        _compile('$test(cases=("a" "b"))\nlet t = (x:int64) => $expect x >? 0\n', test=True)
    assert 't("a")' in str(failure.value)


@needs_toolchain
def test_test_mode_runs_cases_and_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / 'sample.dewy'
    source.write_text(SAMPLE)
    udewy_path = tmp_path / 'sample.test.udewy'
    udewy_path.write_text(codegen(SrcFile.from_path(source), test=True))
    monkeypatch.chdir(tmp_path)
    assert entry_point(udewy_path, []) == 1
    out, err = capfd.readouterr()
    lines = out.splitlines()
    # pytest-shaped: marks first, then each failure's captured output, then the summary
    assert lines[0] == '.........F.'
    assert '--- FAIL fails_on_two[1]' in lines
    assert 'expectation failed' in out and 'two is not welcome' in out and '`x` is 2' in out
    assert '  (1 is fine)' not in out   # a passing test's output is discarded
    assert lines[-1] == '1 failed, 10 passed'
    assert err == '' and 'main is not the entry' not in out
    # machine-readable output
    assert entry_point(udewy_path, ['--json']) == 1
    out, _ = capfd.readouterr()
    records = [json.loads(line) for line in out.splitlines() if line.startswith('{')]
    assert {'test': 'fails_on_two[1]', 'status': 'fail'} in records
    assert records[-1] == {'passed': 10, 'failed': 1}


# ------------------------------------------------------------ `dewy test`

def test_programs_dewy_matches_the_e2e_cases() -> None:
    src = (REPO_ROOT / 'tests' / 'python_misc' / 'test_cleanparse_udewy_e2e.py').read_text()
    cases = [(name, int(code)) for name, code in re.findall(r"^    \('([^']+)', (\d+)\),", src, re.M) if name.endswith('.dewy')]
    programs = (REPO_ROOT / 'tests' / 'dewy' / 'programs.dewy').read_text()
    listed = [(name, int(code)) for name, code in re.findall(r'^    \[name="([^"]+)" expected=(\d+)\]', programs, re.M)]
    assert listed == cases, 'regenerate the cases in tests/dewy/programs.dewy from CASES'


@needs_toolchain
def test_dewy_test_runs_one_module(tmp_path: Path) -> None:
    (tmp_path / 'sample.dewy').write_text(SAMPLE)
    (tmp_path / 'broken.dewy').write_text('$test(cases=("a"))\nlet t = (x:int64) => $expect x >? 0\n')
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get('PYTHONPATH')]))}
    result = subprocess.run([sys.executable, '-m', 'dewy', 'test', 'sample.dewy'], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert result.returncode == 1 and result.stdout.splitlines()[-1] == '1 failed, 10 passed'
    result = subprocess.run([sys.executable, '-m', 'dewy', 'test', 'broken.dewy'], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert result.returncode == 102 and 't("a")' in result.stderr


@needs_toolchain
def test_dewy_test_runs_a_directory(tmp_path: Path) -> None:
    project = tmp_path / 'project'
    (project / 'sub').mkdir(parents=True)
    (project / 'ok_test.dewy').write_text('$test\nlet passes = () => $expect 1 + 1 =? 2\n')
    (project / 'sub' / 'nested_test.dewy').write_text('$test(cases=(1 2))\nlet positive = (x:int64) => $expect x >? 0\n')
    (project / 'bad_test.dewy').write_text('$test\nlet fails = () => $expect 1 =? 2, "one is not two"\n')
    (project / 'plain.dewy').write_text('let main = ():>int64 => 0\n')   # no tests: not built
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(filter(None, [str(REPO_ROOT), os.environ.get('PYTHONPATH')]))}
    result = subprocess.run([sys.executable, '-m', 'dewy', 'test', '.'], cwd=project, env=env, capture_output=True, text=True, timeout=900)
    assert result.returncode == 1, result.stderr
    lines = result.stdout.splitlines()
    assert 'ok_test.dewy .' in lines and 'sub/nested_test.dewy ..' in lines and 'bad_test.dewy F' in lines
    assert 'plain.dewy' not in result.stdout
    assert '--- FAIL fails' in lines and 'one is not two' in result.stdout
    assert lines[-1] == '1 failed in 1 of 3 files'
    result = subprocess.run([sys.executable, '-m', 'dewy', 'test', '--json', '.'], cwd=project, env=env, capture_output=True, text=True, timeout=900)
    assert result.returncode == 1
    records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert records[-1] == {'files': 3, 'failed_files': 1, 'failed': 1}
    assert {'file': 'bad_test.dewy', 'failed': 1} in records
