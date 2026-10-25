"""Programs embedded in the Windows-only tests are built for x86_64-windows on every host, so a
language change that breaks one is caught here rather than only on Windows CI. Building only."""
import importlib
from pathlib import Path

import pytest

from tests.support import compiler  # noqa: F401 (fixture)
from tests.test_cross_target_builds import build

TARGET = 'x86_64-windows'

# (test module, constant holding the program, extension the test writes it with)
PROGRAMS = (
    ('tests.test_windows_cmdline', 'QUOTER', '.jo'),
    ('tests.test_windows_cmdline', 'ECHO', '.dewy'),
    ('tests.test_windows_cmdline', 'RUNNER', '.dewy'),
    ('tests.test_windows_batch', 'DETECTOR', '.jo'),
    ('tests.test_windows_batch', 'RUNNER', '.dewy'),
)


def test_every_windows_test_module_is_registered():
    registered = {module for module, _, _ in PROGRAMS}
    present = {f'tests.{path.stem}' for path in Path(__file__).parent.glob('test_windows_*.py')
               if path != Path(__file__)}
    assert present == registered, f'register programs of {sorted(present ^ registered)}'


@pytest.mark.parametrize(('module', 'name', 'extension'), PROGRAMS,
                         ids=[f'{m.rpartition(".")[2]}-{n}' for m, n, _ in PROGRAMS])
def test_windows_test_program_builds(compiler, tmp_path, module, name, extension):
    toolchain = compiler.parent.parent
    if not (toolchain / 'lib').is_dir():
        pytest.skip(f'{compiler} has no lib/ beside its bin/')
    program = getattr(importlib.import_module(module), name)
    assert isinstance(program, str)
    source = tmp_path / f'{name.lower()}{extension}'
    source.write_text(program)
    built = build(compiler, source, TARGET, tmp_path / f'{name.lower()}.exe', toolchain)
    assert built.returncode == 0, f'{module}.{name} for {TARGET}:\n{built.stdout}{built.stderr}'
