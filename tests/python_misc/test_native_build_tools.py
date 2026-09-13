"""Native build orchestration, using bounded compiler-launcher fixtures."""
import os
from pathlib import Path
import shutil
import subprocess


def test_lto_launcher_keeps_original_compiler_search_path(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for name in ('tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library'):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    script = tmp_path / 'tools/bootstrap_native.sh'
    shutil.copy2(root / 'tools/bootstrap_native.sh', script)
    (tmp_path / 'VERSION').write_text('fixture\n')
    (tmp_path / 'tools/dewy_test.dewy').touch()

    def executable(path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/usr/bin/env bash\nset -eu\n' + body)
        path.chmod(0o755)
        return path

    # Like ccache's masquerading mode, this launcher finds another cc on
    # PATH. Bound recursion so a broken accelerator fails promptly.
    launcher = executable(tmp_path / 'launcher/cc', '''
export TEST_LAUNCHER_DEPTH=$((${TEST_LAUNCHER_DEPTH:-0} + 1))
if (( TEST_LAUNCHER_DEPTH > 3 )); then exit 98; fi
IFS=: read -ra directories <<< "$PATH"
for directory in "${directories[@]}"; do
    candidate="$directory/cc"
    if [[ -x "$candidate" && "$candidate" != "$0" ]]; then
        exec "$candidate" "$@"
    fi
done
exit 99
''')
    backend = executable(tmp_path / 'backend/cc', 'printf "%s\\n" "$*" >> "$TEST_CC_LOG"\n')
    # Stop after exercising the launcher. No fake compiler pair is certified.
    seed = executable(tmp_path / 'seed', 'cc -c fixture.c\nexit 77\n')
    log = tmp_path / 'compiler.log'
    env = os.environ | {
        'PATH': f'{launcher.parent}:{backend.parent}:{os.environ["PATH"]}',
        'DEWY_BOOTSTRAP_LTO_JOBS': '2',
        'TEST_CC_LOG': str(log),
    }
    result = subprocess.run(
        ['bash', script, '--target', 'c', seed, seed, tmp_path / 'pair'],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 77, result.stdout + result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 2  # capability probe and the seed's backend invocation
    assert all(call.split().count('-flto=2') == 1 for call in calls)
    assert not (tmp_path / 'pair/SHA256SUMS').exists()
    assert not list((tmp_path / 'pair').glob('.cc-tools.*'))
