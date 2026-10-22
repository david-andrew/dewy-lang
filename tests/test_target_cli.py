"""`--target` takes the design's target names; others are named precisely."""
import platform
import subprocess

import pytest

from tests.support import compiler  # noqa: F401 (fixture)

PROGRAM = 'main=()=>printl"{$target}"\n'


def build(compiler, tmp_path, target):
    source = tmp_path / 'main.dewy'
    source.write_text(PROGRAM)
    return subprocess.run([compiler, 'build', source, '--target', target, '-o', tmp_path / 'main'],
                          capture_output=True, text=True, timeout=60, check=False)


@pytest.mark.core_quick
def test_processor_alone_is_this_machine(compiler, tmp_path):
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        pytest.skip('the expectation is for an x86-64 Linux host')
    built = build(compiler, tmp_path, 'x86_64')
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([tmp_path / 'main'], capture_output=True, text=True, timeout=10, check=False)
    assert ran.stdout == 'x86_64-linux\n'


@pytest.mark.parametrize('target, message', [
    ('x86_64-mac', "target 'x86_64-mac' is not supported yet (the supported targets are x86_64-linux, "
                   "aarch64-linux, aarch64-mac, x86_64-windows, wasm32)"),
    ('riscv64-freestanding', "target 'riscv64-freestanding' is not supported yet"),
    ('c89', "target 'c89' is not supported yet"),
    ('riscv64', "target 'riscv64' is not supported yet"),
    ('wasm', "unknown target 'wasm' (the supported targets are x86_64-linux, aarch64-linux, aarch64-mac, "
             "x86_64-windows, wasm32); WebAssembly is wasm32"),
    ('linux-arm64', 'Linux on 64-bit ARM is aarch64-linux'),
    ('native', 'the current machine is the default'),
    ('x86-64-linux', "unknown target 'x86-64-linux'"),
])
def test_unsupported_and_unknown_targets(compiler, tmp_path, target, message):
    built = build(compiler, tmp_path, target)
    assert built.returncode == 2, built.stdout + built.stderr
    assert message in built.stderr, built.stderr


def test_other_processor_needs_its_system(compiler, tmp_path):
    if platform.machine() != 'x86_64' or platform.system() != 'Linux':
        pytest.skip('the expectation is for an x86-64 Linux host')
    built = build(compiler, tmp_path, 'aarch64')
    assert built.returncode == 2, built.stdout + built.stderr
    assert ("target 'aarch64' (a processor alone) means this machine, which is x86_64-linux: "
            "name the system too, as aarch64-linux") in built.stderr
