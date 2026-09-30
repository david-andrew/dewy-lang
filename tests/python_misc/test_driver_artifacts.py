"""Shared test drivers are identified by their inputs and never reused across them."""
from pathlib import Path

import driver_artifacts


def _builder(tmp_path: Path, log: list):
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
    log: list = []
    first = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    second = driver_artifacts.shared_driver('probe', source, {'debug': False}, _builder(tmp_path, log))
    assert first == second and len(log) == 1
    assert first.read_text() == 'driver 1'


def test_source_or_options_change_the_identity(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_TEST_DRIVER_DIR', str(tmp_path / 'store'))
    monkeypatch.delenv('DEWY_TEST_DRIVER_CACHE', raising=False)
    source = tmp_path / 'driver.dewy'
    source.write_text('main=():>int64=>42\n')
    log: list = []
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
    log: list = []
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
    log: list = []
    driver_artifacts.shared_driver('probe', source, {}, _builder(tmp_path, log))
    assert len(log) == 1
