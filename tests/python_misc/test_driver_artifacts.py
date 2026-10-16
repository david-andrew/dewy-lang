"""Shared test drivers are identified by their inputs and never reused across them."""
import subprocess
from pathlib import Path

import driver_artifacts
import pytest


@pytest.fixture(autouse=True)
def hosted_by_default(monkeypatch):
    # These harness unit tests choose their own builder, independent of how
    # the surrounding suite was invoked.
    monkeypatch.delenv('DEWY_TEST_DRIVER_COMPILER', raising=False)


class _Log:
    """A build counter kept in a file: builds run in a forked child (`_isolated`)."""

    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / f'build-log-{id(self)}'
        self.path.touch()

    def append(self, entry: int) -> None:
        with open(self.path, 'a') as out:
            out.write(f'{entry}\n')

    def __len__(self) -> int:
        return len(self.path.read_text().splitlines())


def _builder(tmp_path: Path, log: _Log):
    def build() -> Path:
        log.append(1)
        executable = tmp_path / f'built-{len(log)}'
        executable.write_text(f'driver {len(log)}')
        return executable
    return build


def test_same_identity_builds_once(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.delenv('DEWY_TEST_DRIVER_CACHE', raising=False)
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    log = _Log(tmp_path)
    first = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    second = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    assert first == second and len(log) == 1
    assert first.read_text() == 'driver 1'


def test_source_or_options_change_the_identity(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.delenv('DEWY_TEST_DRIVER_CACHE', raising=False)
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    log = _Log(tmp_path)
    base = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    other_options = driver_artifacts.shared_driver('probe', source, {'debug': True}, _builder(tmp_path, log))
    source.write_text('main=():>int64=>41\n')
    edited = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    assert len({base, other_options, edited}) == 3 and len(log) == 3


def test_certification_can_disable_sharing(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.setenv('DEWY_TEST_DRIVER_CACHE', '0')
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    log = _Log(tmp_path)
    driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    assert len(log) == 2 and not (tmp_path / 'store').exists()


def test_failed_build_is_not_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.delenv('DEWY_TEST_DRIVER_CACHE', raising=False)
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')

    def failing() -> Path:
        raise AssertionError('driver build failed')
    try:
        driver_artifacts.shared_driver('probe', source, {}, failing)
    except AssertionError:
        pass
    log = _Log(tmp_path)
    driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    assert len(log) == 1


def test_pruning_spares_entries_in_use(tmp_path, monkeypatch):
    store = tmp_path / 'store'
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(store))
    monkeypatch.delenv('DEWY_TEST_DRIVER_CACHE', raising=False)
    monkeypatch.setattr(driver_artifacts, '_KEEP', 1)
    source = tmp_path / 'driver.dewy'
    log = _Log(tmp_path)
    used = []
    for value in range(3):
        source.write_text(f'main=():>int64=>{value}\n')
        used.append(driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log)))
    # This process still holds every entry it used; none may disappear.
    assert all(path.is_file() for path in used) and len(log) == 3
    # Entries no process holds are pruned down to the kept count.
    for path in used:
        driver_artifacts._held.pop(path.parent).close()
    source.write_text('main=():>int64=>9\n')
    driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    assert sum(1 for path in used if path.is_file()) == 0


def test_native_compiler_content_changes_shared_identity(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.setenv('DEWY_TEST_DRIVER_CACHE', '1')
    compiler = tmp_path / 'dewy'
    compiler.write_text('first compiler')
    compiler.chmod(0o755)
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    log = _Log(tmp_path)
    hosted = driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    monkeypatch.setenv('DEWY_TEST_DRIVER_COMPILER', str(compiler))
    native = driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    compiler.write_text('other compiler')
    rebuilt = driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    assert len({hosted, native, rebuilt}) == 3 and len(log) == 3


@pytest.mark.parametrize('debug', [False, True])
def test_native_emission_keeps_source_target_and_locations(tmp_path, monkeypatch, debug):
    from udewy.cache import cache_artifact

    compiler = tmp_path / 'dewy'
    compiler.touch()
    compiler.chmod(0o755)
    monkeypatch.setenv('DEWY_TEST_DRIVER_COMPILER', str(compiler))
    # Ambient settings must not select a stale library or change the route.
    monkeypatch.setenv('DEWY_LIBRARY_ROOT', '/wrong/library')
    monkeypatch.setenv('DEWY_EMIT', 'native')
    source = tmp_path / 'input with spaces.dewy'
    source.write_text('main=():>int64=>42\n')
    output = tmp_path / 'driver.udewy'

    def run(command, *, cwd, env, **kwargs):
        assert command == [str(compiler), *(['debug', '--build'] if debug else ['-c']),
                           '--target', 'c', str(source)]
        assert env['DEWY_LIBRARY_ROOT'] == str(driver_artifacts.ROOT / 'library')
        assert env['DEWY_EMIT'] == 'udewy'
        assert kwargs['timeout'] > 0
        assert Path(env['DEWY_UDEWY']).is_file()
        emitted = cwd / cache_artifact(source, '.debug.udewy' if debug else '.udewy', cwd=cwd)
        emitted.parent.mkdir(parents=True)
        emitted.write_text('emitted source\n')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(driver_artifacts.subprocess, 'run', run)
    driver_artifacts.isolated_codegen(output, source, target='c', debug_locations=debug)
    assert output.read_text() == 'emitted source\n'
    assert not list(tmp_path.glob('dewy-driver-*'))


@pytest.mark.parametrize('status', [0, 1])
def test_native_failure_never_reuses_stale_output_or_falls_back(tmp_path, monkeypatch, status):
    compiler = tmp_path / 'dewy'
    compiler.touch()
    compiler.chmod(0o755)
    monkeypatch.setenv('DEWY_TEST_DRIVER_COMPILER', str(compiler))
    source = tmp_path / 'driver.dewy'
    source.write_text('not valid Dewy')
    output = tmp_path / 'driver.udewy'
    output.write_text('old source')
    monkeypatch.setattr(driver_artifacts.subprocess, 'run',
                        lambda *a, **k: subprocess.CompletedProcess(a[0], status, '', 'a diagnostic'))
    with pytest.raises(RuntimeError, match='a diagnostic'):
        driver_artifacts.isolated_codegen(output, source)
    assert output.read_text() == 'old source'


def test_missing_native_compiler_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_COMPILER', str(tmp_path / 'missing'))
    with pytest.raises(FileNotFoundError):
        driver_artifacts.isolated_codegen(tmp_path / 'out.udewy', tmp_path / 'in.dewy')


def test_program_output_override_does_not_select_driver_compiler(tmp_path, monkeypatch):
    # bootstrap_program.dewy already uses this name for an executable OUTPUT.
    # Confusing it with the compiler selector could overwrite a compiler.
    monkeypatch.setenv('DEWY_TEST_NATIVE', str(tmp_path / 'program-output'))
    assert driver_artifacts._builder_identity() == {'kind': 'hosted'}


def test_hosted_execution_driver_still_builds_and_runs(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_CACHE', '0')
    source = tmp_path / 'answer.dewy'
    source.write_text('$no_prelude\nmain=():>int64=>42\n')
    binary = driver_artifacts.compiler_driver('answer', source, tmp_path)
    assert subprocess.run([str(binary)], check=False, timeout=10).returncode == 42


@pytest.mark.parametrize('emit_binary', [True, False])
def test_execution_driver_requires_fresh_native_executable(tmp_path, monkeypatch, emit_binary):
    from udewy.cache import cache_artifact

    compiler = tmp_path / 'dewy'
    compiler.touch()
    compiler.chmod(0o755)
    monkeypatch.setenv('DEWY_TEST_DRIVER_COMPILER', str(compiler))
    monkeypatch.setenv('DEWY_TEST_DRIVER_CACHE', '0')
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    output = tmp_path / 'probe-driver.native'
    output.write_text('stale binary')

    def run(command, *, cwd, env, **kwargs):
        assert env['DEWY_EMIT'] == 'native'
        assert command == [str(compiler), '-c', '--target', 'x86_64', str(source)]
        if emit_binary:
            binary = cwd / cache_artifact(source, cwd=cwd)
            binary.parent.mkdir(parents=True)
            binary.write_text('fresh executable')
            binary.chmod(0o755)
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(driver_artifacts.subprocess, 'run', run)
    if emit_binary:
        result = driver_artifacts.compiler_driver('probe', source, tmp_path)
        assert result == output and result.read_text() == 'fresh executable'
        assert result.stat().st_mode & 0o111
    else:
        with pytest.raises(RuntimeError, match='did not build an executable'):
            driver_artifacts.compiler_driver('probe', source, tmp_path)
        assert output.read_text() == 'stale binary'
