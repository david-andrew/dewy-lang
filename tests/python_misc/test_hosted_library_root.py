"""Configured libraries supply both implicit preludes and named imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('relative', [False, True])
def test_configured_library_preserves_module_identity(tmp_path, relative):
    library = tmp_path / 'library'
    shutil.copytree(ROOT / 'library', library)
    reporting = library / 'reporting.dewy'
    with reporting.open('a') as stream:
        stream.write('\nconst configured_answer:int64=42\n')
    source = tmp_path / 'main.dewy'
    source.write_text('''from reporting import configured_answer
import p"library/reporting.dewy" as reports
let accept=(warnings:array<reports.Warning>):>int64=>configured_answer
main=():>int64=>{let warnings:array<Warning>=[] return accept(warnings)}
''')
    env = os.environ | {'PYTHONPATH': str(ROOT),
                        'DEWY_LIBRARY_ROOT': 'library' if relative else str(library)}
    for _ in range(2):
        result = subprocess.run([sys.executable, '-m', 'dewy', source], cwd=tmp_path,
                                env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 42, result.stdout + result.stderr
        # Recompile through the persisted prelude as well as checking cold.
        from udewy.cache import cache_artifact
        (tmp_path / cache_artifact(source, cwd=tmp_path)).unlink()
