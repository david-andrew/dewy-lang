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
    for directory in ['tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library', 'bin']:
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    script = tmp_path / 'tools/bootstrap_native.sh'
    shutil.copyfile(ROOT / 'tools/bootstrap_native.sh', script)
    (tmp_path / 'VERSION').write_text('test\n')
    (tmp_path / 'tools/dewy_test.dewy').write_text('# fixture\n')
    (tmp_path / 'tools/check_native.sh').write_text(
        '#!/bin/sh\nprintf "check %s\\n" "$2" >> "$BOOTSTRAP_TEST_LOG"\n')
    # The real script defers each backend until its caller has exited. Model
    # that protocol, including the C invocation, without compiling a compiler.
    cc = tmp_path / 'bin/cc'
    cc.write_text('''#!/bin/sh
set -eu
[ "$1" = -o ]
cp "$3" "$2"
''')
    cc.chmod(0o755)
    seed = tmp_path / 'seed'
    seed.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help || ${1:-} == --version ]]; then exit 0; fi
[[ $# == 4 && $1 == --target && $3 == -c ]]
printf '%s %s\\n' "$2" "$4" >> "$BOOTSTRAP_TEST_LOG"
if [[ $4 == *.dewy ]]; then
    source="$PWD/__dewycache__/dewy/bootstrap/main.udewy"
    mkdir -p "$(dirname "$source")"
    printf 'fixture\\n' > "$source"
    "$DEWY_UDEWY" --target "$2" -c "$source"
    exit
fi
output="__dewycache__/${4%.*}"
if [[ $4 == /* ]]; then output=${4%.*}; fi
mkdir -p "$(dirname "$output")"
if [[ $2 == c ]]; then cc -o "$output" "$0"; else cp "$0" "$output"; fi
''')
    seed.chmod(0o755)
    log = tmp_path / 'calls'
    output = tmp_path / 'pair'
    option = [] if target == 'x86_64' else ['--target', target]
    result = subprocess.run(['bash', script, *option, seed, seed, output],
                            env={**os.environ, 'BOOTSTRAP_TEST_LOG': str(log),
                                 'PATH': f'{tmp_path / "bin"}:{os.environ["PATH"]}',
                                 'DEWY_BOOTSTRAP_LTO_JOBS': ''},
                            text=True, capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert log.read_text().splitlines() == [
        f'{target} udewy/bootstrap/main.udewy', f'{target} dewy/bootstrap/main.dewy',
        f'{target} {tmp_path}/__dewycache__/dewy/bootstrap/main.udewy',
        'check 1',
        f'{target} udewy/bootstrap/main.udewy', f'{target} dewy/bootstrap/main.dewy',
        f'{target} {tmp_path}/__dewycache__/dewy/bootstrap/main.udewy',
    ]
    assert (output / 'BACKEND').read_text().strip() == target
    assert (output / 'dewy-stage1').read_bytes() == (output / 'dewy-stage2').read_bytes()
