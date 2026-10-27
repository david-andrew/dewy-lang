"""Metal driver failures must not impose panic obligations on game templates."""
import subprocess

from tests.support import compiler  # noqa: F401


def test_game_template_checks_for_macos(compiler, tmp_path):
    game = tmp_path / 'game'
    created = subprocess.run([compiler, 'new', game], capture_output=True, text=True,
                             timeout=30)
    assert created.returncode == 0, created.stdout + created.stderr
    source = game / 'main.dewy'
    # check reads file settings; trailing --target arguments are ignored.
    source.write_text('$target = "aarch64-mac"\n' + source.read_text())
    checked = subprocess.run([compiler, 'check', source], capture_output=True,
                             text=True, timeout=120)
    assert checked.returncode == 0, checked.stdout + checked.stderr
