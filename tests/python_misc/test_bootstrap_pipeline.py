"""Exercise pipeline argument routing with deterministic stand-in executables.

These tests check the build script, not actual compiler self-hosting.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('target', ['x86_64', 'c'])
def test_pipeline_routes_both_compilers_through_selected_backend(tmp_path, target):
    if target == 'c' and shutil.which('cc') is None:
        pytest.skip('C accelerator requires cc')
    for directory in ['tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library']:
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    script = tmp_path / 'tools/bootstrap_native.sh'
    shutil.copyfile(ROOT / 'tools/bootstrap_native.sh', script)
    (tmp_path / 'VERSION').write_text('test\n')
    (tmp_path / 'tools/dewy_test.dewy').write_text('# fixture\n')
    seed = tmp_path / 'seed'
    seed.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help || ${1:-} == --version ]]; then exit 0; fi
[[ $# == 4 && $1 == --target && $3 == -c ]]
printf '%s %s\\n' "$2" "$4" >> "$BOOTSTRAP_TEST_LOG"
output="__dewycache__/${4%.*}"
mkdir -p "$(dirname "$output")"
cp "$0" "$output"
chmod +x "$output"
''')
    seed.chmod(0o755)
    log = tmp_path / 'calls'
    output = tmp_path / 'pair'
    option = [] if target == 'x86_64' else ['--target', target]
    result = subprocess.run(['bash', script, *option, seed, seed, output],
                            env={**os.environ, 'BOOTSTRAP_TEST_LOG': str(log)},
                            text=True, capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text().splitlines() == [
        f'{target} udewy/bootstrap/main.udewy', f'{target} dewy/bootstrap/main.dewy',
        f'{target} udewy/bootstrap/main.udewy', f'{target} dewy/bootstrap/main.dewy',
    ]
    assert (output / 'BACKEND').read_text().strip() == target
    assert (output / 'dewy-stage1').read_bytes() == (output / 'dewy-stage2').read_bytes()
