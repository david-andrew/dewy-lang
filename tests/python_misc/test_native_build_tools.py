"""Native build orchestration, using bounded compiler-launcher fixtures."""
import os
from pathlib import Path
import shutil
import subprocess


def test_backend_runs_after_dewy_exits_and_failure_stops_build(tmp_path):
    root = Path(__file__).resolve().parents[2]
    work = tmp_path / 'checkout with spaces'
    for name in ('tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library'):
        (work / name).mkdir(parents=True, exist_ok=True)
    script = work / 'tools/bootstrap_native.sh'
    shutil.copy2(root / 'tools/bootstrap_native.sh', script)
    (work / 'VERSION').write_text('fixture\n')
    (work / 'tools/dewy_test.dewy').touch()
    dewy = work / 'dewy-seed'
    dewy.write_text('''#!/usr/bin/env bash
set -eu
echo "$$" > "$TEST_DEWY_PID"
mkdir -p __dewycache__/dewy/bootstrap
source="$PWD/__dewycache__/dewy/bootstrap/main.udewy"
echo 'let main=()=>42' > "$source"
"$DEWY_UDEWY" --target "$2" -c "$source"
echo emitted > "$TEST_DEWY_DONE"
''')
    micro = work / 'udewy-seed'
    micro.write_text('''#!/usr/bin/env bash
set -eu
if [[ $4 == udewy/bootstrap/main.udewy ]]; then
    mkdir -p __dewycache__/udewy/bootstrap
    cp "$0" __dewycache__/udewy/bootstrap/main
    exit 0
fi
[[ -f "$TEST_DEWY_DONE" ]]
if kill -0 "$(cat "$TEST_DEWY_PID")" 2>/dev/null; then exit 98; fi
[[ $# == 4 && $1 == --target && $2 == x86_64 && $3 == -c && -s $4 ]]
printf '%s\\n' "$4" > "$TEST_BACKEND_SOURCE"
exit 77
''')
    dewy.chmod(0o755)
    micro.chmod(0o755)
    env = os.environ | {
        'TEST_DEWY_PID': str(work / 'dewy.pid'),
        'TEST_DEWY_DONE': str(work / 'dewy.done'),
        'TEST_BACKEND_SOURCE': str(work / 'backend.source'),
    }
    result = subprocess.run(['bash', script, dewy, micro, work / 'pair'],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 77, result.stdout + result.stderr
    assert (work / 'backend.source').read_text().strip() == str(work / '__dewycache__/dewy/bootstrap/main.udewy')
    assert not (work / 'pair/SHA256SUMS').exists()
    assert not list((work / 'pair').glob('.backend-handoff.*'))


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
