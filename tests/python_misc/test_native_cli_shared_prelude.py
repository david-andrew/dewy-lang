"""Fresh native build directories reuse the checked library, not program output."""
import os
import subprocess
from pathlib import Path

import pytest

from udewy.cache import cache_artifact

ROOT = Path(__file__).resolve().parents[2]


def test_native_cli_reuses_prelude_across_build_directories(tmp_path):
    compiler = os.environ.get('DEWY_CACHE_TEST_COMPILER')
    if not compiler:
        pytest.skip('set DEWY_CACHE_TEST_COMPILER to the current native CLI')
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(XDG_CACHE_HOME=str(tmp_path / 'user-cache'),
               DEWY_LIBRARY_ROOT=str(ROOT / 'library'), DEWY_FAILURE_LOG='0')

    def build(name, expected, **overrides):
        work = tmp_path / name
        work.mkdir()
        source = work / 'main.dewy'
        source.write_text(f'main=():>int64=>{expected}\n')
        built = subprocess.run([compiler, '--timings', '-c', str(source)], cwd=work,
                               env=env | overrides, capture_output=True, text=True,
                               timeout=45, check=False)
        assert built.returncode == 0, built.stdout + built.stderr
        binary = work / cache_artifact(source, cwd=work)
        run = subprocess.run([binary], capture_output=True, timeout=10, check=False)
        assert run.returncode == expected, (run.returncode, run.stderr)
        return built.stderr

    cold = build('first-project', 42)
    assert 'dewy timing prelude_store ' in cold
    entries = list((tmp_path / 'user-cache/dewy/prelude').glob('native-*.bin'))
    assert len(entries) == 1
    warm = build('second-project', 43)
    assert 'dewy timing prelude_restore ' in warm
    assert 'dewy timing prelude_store ' not in warm
    # A shared cache remains optional and self-repairing.
    entries[0].write_bytes(b'interrupted cache')
    repaired = build('third-project', 44)
    assert 'dewy timing prelude_store ' in repaired
    assert entries[0].stat().st_size > 100
    isolated = tmp_path / 'isolated-prelude'
    explicit = build('fourth-project', 45, DEWY_PRELUDE_CACHE_DIR=str(isolated))
    assert 'dewy timing prelude_store ' in explicit
    assert len(list(isolated.glob('native-*.bin'))) == 1
