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
    backend = executable(tmp_path / 'backend/cc', 'printf "%s\\n" "$*" >> "$TEST_CC_LOG"\nif [[ $* == *fixture.c* ]]; then exit 77; fi\n')
    # Stop after exercising the launcher. No fake compiler pair is certified.
    seed = executable(tmp_path / 'seed', 'cc -c fixture.c\n')
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


def test_first_generation_execution_failure_prevents_second_build(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for name in ('tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library'):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    for name in ('bootstrap_native.sh', 'check_native.sh'):
        shutil.copy2(root / 'tools' / name, tmp_path / 'tools' / name)
    (tmp_path / 'VERSION').write_text('fixture\n')
    (tmp_path / 'tools/dewy_test.dewy').touch()
    seed = tmp_path / 'dewy-seed'
    seed.write_text('''#!/usr/bin/env bash
set -eu
if [[ $1 == --version ]]; then exit 0; fi
if [[ $3 != -c ]]; then exit 17; fi
mkdir -p __dewycache__/dewy/bootstrap
cp "$0" __dewycache__/dewy/bootstrap/main
source="$PWD/__dewycache__/dewy/bootstrap/main.udewy"
echo 'let main=()=>42' > "$source"
"$DEWY_UDEWY" --target "$2" -c "$source"
''')
    micro = tmp_path / 'udewy-seed'
    micro.write_text('''#!/usr/bin/env bash
set -eu
if [[ $1 == --help || ${3:-} != -c ]]; then exit 0; fi
if [[ $4 == udewy/bootstrap/main.udewy ]]; then
    mkdir -p __dewycache__/udewy/bootstrap
    cp "$0" __dewycache__/udewy/bootstrap/main
fi
''')
    seed.chmod(0o755)
    micro.chmod(0o755)
    pair = tmp_path / 'pair'
    result = subprocess.run(['bash', tmp_path / 'tools/bootstrap_native.sh', seed, micro, pair],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'Expected exit 42, got 17' in result.stderr
    assert (pair / 'dewy-stage1').exists()
    assert not (pair / 'udewy-stage2').exists()
    assert not (pair / 'SHA256SUMS').exists()


def test_c_backend_runs_after_micro_compiler_exits(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for name in ('tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library', 'bin'):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    script = tmp_path / 'tools/bootstrap_native.sh'
    shutil.copy2(root / 'tools/bootstrap_native.sh', script)
    (tmp_path / 'VERSION').write_text('fixture\n')
    (tmp_path / 'tools/dewy_test.dewy').touch()
    seed = tmp_path / 'seed'
    seed.write_text('''#!/usr/bin/env bash
set -eu
echo "$$" > "$TEST_MICRO_PID"
cc -std=c99 -O2 -o 'output with spaces' 'source with spaces.c'
''')
    compiler = tmp_path / 'bin/cc'
    compiler.write_text('''#!/usr/bin/env bash
set -eu
if kill -0 "$(cat "$TEST_MICRO_PID")" 2>/dev/null; then exit 98; fi
printf '%s\\0' "$@" > "$TEST_CC_ARGUMENTS"
exit 77
''')
    seed.chmod(0o755)
    compiler.chmod(0o755)
    arguments = tmp_path / 'arguments'
    env = os.environ | {
        'PATH': f'{compiler.parent}:{os.environ["PATH"]}',
        'TEST_MICRO_PID': str(tmp_path / 'micro.pid'),
        'TEST_CC_ARGUMENTS': str(arguments),
    }
    env.pop('DEWY_BOOTSTRAP_LTO_JOBS', None)
    result = subprocess.run(['bash', script, '--target', 'c', seed, seed, tmp_path / 'pair'],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 77, result.stdout + result.stderr
    assert arguments.read_bytes().split(b'\0') == [
        b'-std=c99', b'-O2', b'-o', b'output with spaces', b'source with spaces.c', b'',
    ]
    assert not (tmp_path / 'pair/SHA256SUMS').exists()


def interrupted_pair(tmp_path):
    """A saved generation whose execution check failed before generation two."""
    root = Path(__file__).resolve().parents[2]
    for name in ('tools', 'dewy/bootstrap', 'udewy/bootstrap', 'udewy/stdlib', 'library'):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    script = tmp_path / 'tools/bootstrap_native.sh'
    shutil.copy2(root / 'tools/bootstrap_native.sh', script)
    (tmp_path / 'VERSION').write_text('fixture\n')
    (tmp_path / 'tools/dewy_test.dewy').touch()
    (tmp_path / 'tools/check_native.sh').write_text(
        '#!/bin/sh\necho check >> "$TEST_LOG"\nexit "${TEST_CHECK_STATUS:-0}"\n')
    dewy = tmp_path / 'dewy-seed'
    dewy.write_text('''#!/usr/bin/env bash
set -eu
if [[ $1 == --version ]]; then exit 0; fi
echo dewy >> "$TEST_LOG"
mkdir -p __dewycache__/dewy/bootstrap
source="$PWD/__dewycache__/dewy/bootstrap/main.udewy"
echo 'let main=()=>42' > "$source"
"$DEWY_UDEWY" --target "$2" -c "$source"
''')
    micro = tmp_path / 'udewy-seed'
    micro.write_text('''#!/usr/bin/env bash
set -eu
if [[ $1 == --help ]]; then exit 0; fi
if [[ $4 == udewy/bootstrap/main.udewy ]]; then
    echo micro >> "$TEST_LOG"
    mkdir -p __dewycache__/udewy/bootstrap
    cp "$0" __dewycache__/udewy/bootstrap/main
else
    cp "$TEST_DEWY_SEED" __dewycache__/dewy/bootstrap/main
fi
''')
    dewy.chmod(0o755)
    micro.chmod(0o755)
    env = os.environ | {'TEST_LOG': str(tmp_path / 'calls'),
                        'TEST_DEWY_SEED': str(dewy), 'TEST_CHECK_STATUS': '77'}
    command = ['bash', str(script), str(dewy), str(micro), str(tmp_path / 'pair')]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 77, result.stdout + result.stderr
    assert (tmp_path / 'pair/GENERATION_1_SHA256SUMS').exists()
    assert not (tmp_path / 'pair/SHA256SUMS').exists()
    return command, env


def test_resume_rechecks_saved_generation_without_rebuilding_it(tmp_path):
    command, env = interrupted_pair(tmp_path)
    # A repeated failed check must still prevent generation two.
    resumed = command[:2] + ['--resume'] + command[2:]
    result = subprocess.run(resumed, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 77, result.stdout + result.stderr
    assert (tmp_path / 'calls').read_text().splitlines() == ['micro', 'dewy', 'check', 'check']
    env['TEST_CHECK_STATUS'] = '0'
    result = subprocess.run(resumed, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / 'calls').read_text().splitlines() == [
        'micro', 'dewy', 'check', 'check', 'check', 'micro', 'dewy']
    assert (tmp_path / 'pair/SHA256SUMS').exists()
    assert not list((tmp_path / 'pair').glob('.backend-handoff.*'))


def test_resume_rejects_modified_saved_inputs(tmp_path):
    # Each rejection occurs before invoking even the execution-check helper.
    for name in ('source', 'binary', 'seed', 'options', 'missing'):
        work = tmp_path / name
        command, env = interrupted_pair(work)
        if name == 'source':
            (work / 'VERSION').write_text('changed\n')
        elif name == 'binary':
            (work / 'pair/dewy-stage1').write_text('changed\n')
        elif name == 'seed':
            (work / 'dewy-seed').write_text('changed\n')
        elif name == 'options':
            env['DEWY_BOOTSTRAP_LTO_JOBS'] = '2'
        else:
            (work / 'pair/GENERATION_1_SHA256SUMS').unlink()
        result = subprocess.run(command[:2] + ['--resume'] + command[2:], env=env,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode != 0, name
        assert (work / 'calls').read_text().splitlines() == ['micro', 'dewy', 'check']
        assert not (work / 'pair/SHA256SUMS').exists()
