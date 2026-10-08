"""Shared test drivers are identified by their inputs and never reused across them."""
from pathlib import Path

import driver_artifacts


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
