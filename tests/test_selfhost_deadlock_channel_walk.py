"""Demanded channel/task collection agrees with the frozen implementation."""
from tests.support import compiler  # noqa: F401
from tests.test_selfhost_deadlock_channels import compare_channels


def test_deadlock_channel_walk_twins(compiler, tmp_path, monkeypatch):
    compare_channels(compiler, tmp_path, monkeypatch, 'deadlock_channel_walk')
