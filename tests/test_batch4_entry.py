"""Only the invoked file owns the entry point; library test mains stay local."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
@pytest.mark.parametrize(('source', 'expected'), [
    ('import p"lib.dewy"\nmain=()=>printl"app {helper}"\n', 'app 7\n'),
    ('import p"lib.dewy"\nprintl(helper)\n', '7\n'),
    ('import p"lib.dewy"\nimport p"other.dewy"\nmain=()=>printl(helper+other_helper)\n', '15\n'),
    ('from p"lib.dewy" import main\nprintl"script"\n', 'script\n'),
    ('from p"lib.dewy" import (main as local_test)\nlocal_test()\n', 'library\n'),
    ('import p"lib.dewy" as lib\nmain=()=>lib.main()\n', 'library\n'),
])
def test_batch4_entry(compiler, tmp_path, release, source, expected):
    library = tmp_path / 'lib.dewy'
    library.write_text('helper=()=>7\nmain=()=>printl"library"\n')
    (tmp_path / 'other.dewy').write_text('other_helper=()=>8\nmain=()=>printl"other library"\n')
    app = tmp_path / 'app.dewy'
    app.write_text(source)
    flags = ['--release'] if release else []
    for entry, output in [(app, expected), (library, 'library\n')]:
        result = subprocess.run([compiler, 'run', *flags, entry], capture_output=True,
                                text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert result.stdout == output


@pytest.mark.parametrize(('source', 'name'), [
    ('import p"lib.dewy"\nhelper=()=>8\nmain=()=>printl(helper)\n', 'helper'),
    ('from p"lib.dewy" import main\nmain=()=>printl"app"\n', 'main'),
])
def test_batch4_entry_keeps_explicit_collisions(compiler, tmp_path, source, name):
    (tmp_path / 'lib.dewy').write_text('helper=()=>7\nmain=()=>printl"library"\n')
    app = tmp_path / 'app.dewy'
    app.write_text(source)
    result = subprocess.run([compiler, 'check', app], capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert f"cannot import '{name}'" in result.stderr
