"""Batched golden cases keep a module's top-level output, judging each case as it runs alone."""
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


def run(compiler, root, tmp_path, monkeypatch):
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    return cases.run(compiler, cases.discover(root), workers=2)


@pytest.mark.core_quick
def test_core_case_top_level_output(compiler, tmp_path, monkeypatch, capsys):
    root = tmp_path / 'cases'
    for i in range(3):
        write(root, f'plain{i}', f'# modes: native\nmain=()=>{{printl"plain {i}"}}\n', out=f'plain {i}\n')
    write(root, 'top', '# modes: native\nprintl"top"\nmain=()=>{printl"main"}\n', out='top\nmain\n')
    write(root, 'top_panics', '# modes: native\n# exit: 101\nprintl"top"\nmain=()=>{printl"main" panic("boom")}\n',
          out='top\nmain\n', err='boom\n')
    write(root, 'panics', '# modes: native\n# exit: 101\nmain=()=>{printl"main" panic("boom")}\n',
          out='main\n', err='boom\n')
    assert run(compiler, root, tmp_path, monkeypatch) == 0
    # Without its top-level line the expectation is wrong, batched or not.
    write(root, 'top', '# modes: native\nprintl"top"\nmain=()=>{printl"main"}\n', out='main\n')
    assert run(compiler, root, tmp_path, monkeypatch) == 1
    assert 'FAIL top [native]' in capsys.readouterr().out
