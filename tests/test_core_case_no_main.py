"""A golden case with no main (top-level code only) runs alone from the start: no batch build
is spent on it."""
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


def test_core_case_no_main_plan(tmp_path):
    write(tmp_path, 'script', '# modes: native\nprintl"top"\n', out='top\n')
    write(tmp_path, 'script_panics', '# modes: native\n# exit: 101\nlet xs:array<int64>=[]\nprintl(xs[1])\n',
          err='out of bounds\n')
    write(tmp_path, 'with_main', '# modes: native\nmain=()=>{printl"main"}\n', out='main\n')
    write(tmp_path, 'let_main', '# modes: native\nlet main = () => {printl"let"}\n', out='let\n')
    write(tmp_path, 'commented', '# modes: native\n# main=()=>0\nprintl"x"\n', out='x\n')
    units = cases.plan(cases.discover(tmp_path), node=False)
    kinds = {case.name: kind for kind, _, chosen in units for case in chosen}
    assert kinds == {'script': 'single', 'script_panics': 'single', 'with_main': 'value', 'let_main': 'value',
                     'commented': 'single'}


@pytest.mark.core_quick
def test_core_case_no_main_builds_once(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'cases'
    write(root, 'script', '# modes: native\nprintl"top"\n', out='top\n')
    write(root, 'with_main', '# modes: native\nmain=()=>{printl"main"}\n', out='main\n')
    builds = []
    original = cases.Runner.build

    def counted(self, source, output, mode):
        builds.append(source.name)
        return original(self, source, output, mode)

    monkeypatch.setattr(cases.Runner, 'build', counted)
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    assert cases.run(compiler, cases.discover(root), workers=2) == 0
    assert sorted(builds) == ['batch.dewy', 'script.dewy'], builds
