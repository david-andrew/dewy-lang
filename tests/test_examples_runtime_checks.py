"""Published examples should need no opt-in: common crashes are impossible unless opted into.

A ratchet on the metric itself: an example may leave this list, and none may join it. Each listed
one says what stops it. Every example must also still compile as it stands."""
import os
import re
import subprocess
from pathlib import Path

from tests.support import compiler  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r'^\s*\$runtime_checks\b', re.M)

# Physics handles may name a removed body: open decision D11c.
NEEDS_THE_TAG = {'physics', 'physics_scene'}


def test_examples_carry_no_new_opt_in(compiler, tmp_path):  # noqa: F811
    env = dict(os.environ, DISPLAY='', WAYLAND_DISPLAY='', DEWY_NO_AUDIO='1')
    tagged = set()
    for source in sorted((ROOT / 'examples').glob('*.dewy')):
        if TAG.search(source.read_text()):
            tagged.add(source.stem)
        checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, env=env,
                                 cwd=tmp_path, timeout=60, check=False)
        assert checked.returncode == 0, source.name + '\n' + checked.stdout + checked.stderr
    assert tagged == NEEDS_THE_TAG
