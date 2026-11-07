"""The same time programs give the same answers on Linux arm64 (qemu); other targets at least build."""
import shutil
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

PROGRAM = """let t = instant"2026-10-24T12:00:00Z"
printl"{t + 90minute} {(t + 90minute) - t}"
const meet = zoned"2026-10-26T09:00[America/New_York]"
printl"{meet + 1week} {meet.format("EEEE HH:mm XXX")}"
let text = "2026-03-08T02:30"
printl(zoned(text zone=zone"America/New_York" gap='next'))
printl(zoned("2040-07-01T12:00" zone=zone"Australia/Lord_Howe"))
printl"{(date"2026-12-25" - date"2024-10-24").total_days} {date"2027-01-31".add(1month overflow='clamp')}"
printl"{t in? [t..t+1s)} {(t+1s) in? [t..t+1s)} {[t..t+1s)}"
let [d lost] = quantize(1ns/3 rounding='nearest_even')
printl"{d} {lost}"
const packed = convert<Instant<width=64>>(instant"2026-10-24T12:00:00Z")
printl(packed + 1s)
let began = now
sleep(1ms)
printl"{now - began >? 500us} {monotonic <=? monotonic}"
"""


def build(compiler, tmp_path, target, name):
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAM)
    return subprocess.run([compiler, 'build', source, '--target', target, '-o', tmp_path / name], capture_output=True,
                          text=True, timeout=300, check=False, cwd=tmp_path)


def test_arm64_linux_answers_the_same(compiler, tmp_path):
    runner = shutil.which('qemu-aarch64')
    if runner is None:
        pytest.skip('no qemu-aarch64')
    built = build(compiler, tmp_path, 'x86_64-linux', 'native')
    assert built.returncode == 0, built.stderr
    native = subprocess.run([tmp_path / 'native'], capture_output=True, text=True, timeout=60, check=False)
    built = build(compiler, tmp_path, 'aarch64-linux', 'arm')
    assert built.returncode == 0, built.stderr
    arm = subprocess.run([runner, tmp_path / 'arm'], capture_output=True, text=True, timeout=120, check=False)
    assert arm.returncode == 0, arm.stderr
    assert arm.stdout == native.stdout
    assert len(native.stdout.splitlines()) == 9


@pytest.mark.parametrize('target', ['x86_64-windows', 'aarch64-mac', 'wasm32'])
def test_other_targets_build(compiler, tmp_path, target):
    built = build(compiler, tmp_path, target, 'program')
    assert built.returncode == 0, built.stderr
