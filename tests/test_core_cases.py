"""The golden-case runner: headers, batching fallbacks and output recording."""
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tools import cases


def write(root, name, source, out=None, err=None):
    path = root / f'{name}.dewy'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    if out is not None:
        path.with_suffix('.out').write_text(out)
    if err is not None:
        path.with_suffix('.err').write_text(err)
    return path


def run(compiler, root, tmp_path, monkeypatch, **options):
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    return cases.run(compiler, cases.discover(root), workers=2, **options)


def test_core_case_headers(tmp_path):
    path = write(tmp_path, 'a/header', '# exit: 42\n# modes: native web-release\n# args: one "two three"\n'
                 '# stdin: x\\ny\n# quick\n# An ordinary comment: not a header.\nmain=()=>42\n')
    case = cases.parse(path, tmp_path)
    assert (case.name, case.exit, case.modes, case.args, case.stdin, case.quick, case.kind) == (
        'a/header', 42, ('native', 'web-release'), ('one', 'two three'), b'x\ny', True, 'run')
    write(tmp_path, 'a/typo', '# exti: 1\nmain=()=>0\n')
    with pytest.raises(cases.CaseError, match='unknown header key'):
        cases.parse(tmp_path / 'a/typo.dewy', tmp_path)
    assert cases.keyword_filter('header and not typo')('a/header')
    assert not cases.keyword_filter('header and not typo')('a/typo')


def test_core_case_batch_fallbacks(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    write(root, 'value', '# exit: 42\nmain=()=>{printl"value 🙂" return 42}\n', out='value 🙂\n')
    write(root, 'void', 'main=()=>{if false {return} printl"void"}\n', out='void\n')
    write(root, 'exits', '# modes: native web\n# exit: 3\nmain=()=>{exit(3) return 0}\n')
    write(root, 'after', 'let g=7\nmain=()=>{printl"{g}" return 0}\n', out='7\n')
    write(root, 'panics', '# exit: 101\nmain=():>int64=>{printl"before" let xs:array<int64>=[] return xs[1]}\n',
          out='before\n', err='out of bounds\n/index \\d+ out of bounds/\n')
    write(root, 'rejects', '# modes: native\nmain=()=>{let x:int64="no" return 0}\n', err='type mismatch\n')
    write(root, 'arguments', '# modes: native native-release\n# args: a b\nmain=()=>{printl(args().length) return 0}\n',
          out='3\n')
    assert run(compiler, root, tmp_path, monkeypatch) == 0


def test_core_case_failures(compiler, tmp_path, monkeypatch, capsys):
    root = tmp_path / 'cases'
    write(root, 'wrong-exit', '# modes: native native-release\nmain=()=>1\n')
    write(root, 'wrong-output', '# modes: native\nmain=()=>{printl"actual" return 0}\n', out='expected\n')
    write(root, 'broken', '# modes: native\nmain=()=>missing_name\n')
    write(root, 'compiles', '# modes: native\nmain=()=>0\n', err='an error\n')
    assert run(compiler, root, tmp_path, monkeypatch) == 1
    report = capsys.readouterr().out
    assert 'FAIL wrong-exit [native native-release]' in report and 'exit 1, expected 0' in report
    assert '-expected\n' in report and '+actual\n' in report
    assert 'FAIL broken [native]' in report and 'missing_name' in report
    assert 'FAIL compiles [native]' in report and 'compiled, but a diagnostic was expected' in report
    assert '0 passed, 4 failed' in report


def test_core_case_update(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    new = write(root, 'new', '# modes: native\nmain=()=>{printl"fresh" return 0}\n')
    old = write(root, 'old', '# modes: native\nmain=()=>{printl"now" return 0}\n', out='before\n')
    assert run(compiler, root, tmp_path, monkeypatch, update=True) == 1
    assert old.with_suffix('.out').read_text() == 'now\n' and not new.with_suffix('.out').exists()
    assert run(compiler, root, tmp_path, monkeypatch, update=True, explicit=True) == 0
    assert new.with_suffix('.out').read_text() == 'fresh\n'


def test_core_case_combined_failure(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    for name in ('first', 'last'):
        write(root, name, '# modes: native\nmain=()=>0\n')
    original = cases.Runner.execute

    def fail_combined(self, command, *args, **kwargs):
        if Path(command[-1]).name == 'batch' and (Path(command[-1]).parent / 'batch.dewy').read_text().count(
                'import') > 1:
            return 7, '', 'injected failure requiring the combined program'
        return original(self, command, *args, **kwargs)

    monkeypatch.setattr(cases.Runner, 'execute', fail_combined)
    assert run(compiler, root, tmp_path, monkeypatch) == 1
