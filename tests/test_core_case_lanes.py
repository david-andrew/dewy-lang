"""Batch lanes, direct-call void probes, form guesses and persistent Node execution."""
from __future__ import annotations

import shutil

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


@pytest.mark.core_quick
def test_initial_form_and_plan_lanes(tmp_path):
    assert cases.initial_form('main=():>void=>{printl"x"}\n') == 'void'
    assert cases.initial_form('let main = ():>void => { printl"x" }\n') == 'void'
    assert cases.initial_form('main = ():>void & no panics => { printl"x" }\n') == 'void'
    assert cases.initial_form('main = () => { f = () => { return 1 } printl(f()) }\n') == 'guess'
    assert cases.initial_form('main = () => { let x = f() or_throw printl(x) }\n') == 'value'
    assert cases.initial_form('main = () => exit(run())\n') == 'value'
    assert cases.initial_form('main = ():>void => exit(run())\n') == 'value'
    assert cases.entry_name('main = ():>void => exit(run())\n') == 'run'

    write(tmp_path, 'strict_case', '# modes: native\nmain=()=>{printl"s"}\n', out='s\n')
    write(tmp_path, 'checked_case', '# modes: native\n$runtime_checks\nmain=()=>{printl"c"}\n', out='c\n')
    write(tmp_path, 'direct_exit', '# modes: native\n# exit: 7\nmain=():>void=>exit(7)\n')
    write(tmp_path, 'takes_args', '# modes: native\nmain=(argv:array<string>)=>{printl(argv.length)}\n', out='1\n')

    units = cases.plan(cases.discover(tmp_path), node=False)
    by_unit = {(kind, tuple(c.name for c in batch)) for kind, _, batch in units}
    assert by_unit == {
        ('value', ('strict_case',)),
        ('value', ('checked_case',)),
        ('panic', ('direct_exit',)),
        ('single', ('takes_args',)),
    }


@pytest.mark.core_quick
def test_checked_and_owned_cases_build_without_retries(compiler, tmp_path, monkeypatch):  # noqa: F811
    root = tmp_path / 'cases'
    write(root, 'checked_ok', '# modes: native\n$runtime_checks\nmain=():>void=>{let xs=[1 2] printl(xs[1])}\n',
          out='2\n')
    write(root, 'owned_void',
          '# modes: native\nlet drops:int64=0\nOwner=type of [v:int64 $__drop__=():>void=>{drops+=1}]\n'
          'main=()=>{{let o=Owner[1]} printl"drops {drops}"}\n',
          out='drops 1\n')
    write(root, 'panic_ok',
          '# modes: native\n# exit: 101\n$runtime_checks\nmain=():>void=>{let xs:array<int64>=[] printl(xs[0])}\n',
          err='out of bounds\n')

    builds = []
    original = cases.Runner.build

    def counted(self, source, output, mode):
        builds.append(source.name)
        return original(self, source, output, mode)

    monkeypatch.setattr(cases.Runner, 'build', counted)
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    assert cases.run(compiler, cases.discover(root), workers=1) == 0
    # One build for strict owned_void, one for checked_ok, one for panic_ok — zero retries.
    assert builds == ['batch.dewy', 'batch.dewy', 'batch.dewy'], builds


@pytest.mark.core_quick
def test_strict_wrapper_still_rejects_broken_strict_case(compiler, tmp_path):  # noqa: F811
    # `$runtime_checks` on a checked batch wrapper is module-local and never
    # weakens no-traps checking inside an imported strict case module.
    broken = write(tmp_path, 'broken_strict',
                   'main=():>void=>{let xs:array<int64>=[1 2] let i:int64=1 printl(xs[i + 5])}\n')
    case = cases.parse(broken, tmp_path)
    source, _ = cases.batch_source([case], ['void'], select=False, checked=True)
    wrapper = tmp_path / 'batch.dewy'
    wrapper.write_text(source)
    runner = cases.Runner(compiler, tmp_path, cases.clean_environment())
    built = runner.build(wrapper, tmp_path / 'batch', 'native')
    assert built.returncode != 0
    assert 'out of bounds' in built.stderr or 'not in bounds' in built.stderr


@pytest.mark.core_quick
def test_persistent_node_worker_web_and_panic(compiler, tmp_path, monkeypatch):  # noqa: F811
    if shutil.which('node') is None:
        pytest.skip('node is not installed')
    root = tmp_path / 'cases'
    write(root, 'web_ok', '# modes: web\nmain=():>void=>{printl"hello 🙂"}\n', out='hello 🙂\n')
    write(root, 'web_exit', '# modes: web\n# exit: 9\nmain=():>void=>{printl"bye" exit(9)}\n', out='bye\n')
    write(root, 'web_panic',
          '# modes: web\n# exit: 101\n$runtime_checks\nmain=():>void=>{printl"pre" let xs:array<int64>=[] printl(xs[0])}\n',
          out='pre\n', err='out of bounds\n')
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    assert cases.run(compiler, cases.discover(root), workers=1) == 0


@pytest.mark.core_quick
def test_node_subprocess_fallback_when_worker_disabled(compiler, tmp_path, monkeypatch):  # noqa: F811
    if shutil.which('node') is None:
        pytest.skip('node is not installed')
    root = tmp_path / 'cases'
    write(root, 'web_fallback', '# modes: web\nmain=():>void=>{printl"win-ok"}\n', out='win-ok\n')
    monkeypatch.setattr(cases, 'USE_NODE_WORKER', False)
    monkeypatch.setattr(cases.Runner, '_node_worker', lambda self: pytest.fail('persistent Node worker must not start'))
    monkeypatch.setenv('TMPDIR', str(tmp_path))
    monkeypatch.setattr(cases.tempfile, 'tempdir', None)
    assert cases.run(compiler, cases.discover(root), workers=1) == 0
