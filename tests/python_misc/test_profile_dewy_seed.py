"""Exercise actual GCC counter production/use, including an untrained path."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('flush_profiles', [True, False])
def test_seed_profile_pipeline_requires_real_counters(tmp_path, flush_profiles):
    gcc = shutil.which('gcc')
    if gcc is None:
        pytest.skip('GCC is required for this optional seed optimization')
    source = tmp_path / 'seed.c'
    source.write_text('''#include <stdlib.h>
int main(int argc, char **argv) {
    volatile int count = argc;
    if (count == 1) return 42;
''' + ('return 0;' if flush_profiles else '_Exit(0);') + '\n}\n')
    training = tmp_path / 'training.dewy'
    training.write_text('main=():>int64=>42\n')
    output = tmp_path / 'profile output'
    result = subprocess.run(['bash', str(ROOT / 'tools/profile_dewy_seed.sh'),
                             str(source), str(output), str(training)],
                            env=os.environ | {'DEWY_PGO_CC': gcc, 'DEWY_UDEWY': '/usr/bin/true',
                                              'DEWY_BOOTSTRAP_LTO_JOBS': '1'},
                            capture_output=True, text=True, timeout=30, check=False)
    if not flush_profiles:
        assert result.returncode == 1
        assert 'no GCC profile counters' in result.stderr
        assert not (output / 'compiler.sha256').exists()
        return
    assert result.returncode == 0, result.stdout + result.stderr
    assert (output / 'compiler.sha256').is_file()
    assert (output / 'compiler.instrumented').is_file()
    assert list((output / 'profiles').rglob('*.gcda'))
    assert subprocess.run([output / 'compiler'], check=False).returncode == 42
