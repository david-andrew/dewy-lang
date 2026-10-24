"""Program run directories live on /dev/shm when usable and are removed afterwards."""
import pytest

from tools import scratch


def test_run_dir_removed_on_success_and_failure(tmp_path, monkeypatch):
    if not scratch.SHM.is_dir():
        pytest.skip('no /dev/shm')
    monkeypatch.delenv('DEWY_RUN_ON_DISK', raising=False)
    with scratch.run_dir('a/b', tmp_path) as made:
        assert made.parent == scratch.SHM and made.name.startswith(scratch.RUN_PREFIX)
        (made / 'data').write_text('x')
    assert not made.exists()
    with pytest.raises(RuntimeError):
        with scratch.run_dir('fail', tmp_path) as made:
            raise RuntimeError
    assert not made.exists()


def test_run_dir_override_uses_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_RUN_ON_DISK', '1')
    with scratch.run_dir('x', tmp_path) as made:
        assert made == tmp_path
