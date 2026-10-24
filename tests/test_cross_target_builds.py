"""Cross-target builds: code under an untaken `$target` branch is never type-checked on
this host, so build the compiler itself and the programs that use `$target` for every
other target. Building only; foreign binaries are not run."""
import os
import platform
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401 (fixture)

TARGETS = ('x86_64-windows', 'aarch64-mac', 'aarch64-linux', 'wasm32', 'x86_64-linux')

# Programs whose imports (lib/net.dewy) or own source branch on `$target`.
PROGRAMS = ('examples/netpong.dewy', 'examples/rollback_lab.dewy',
            'tests/ladder/111_build_aware/design.dewy',
            'tests/ladder/23_tcp_echo/core.dewy', 'tests/ladder/24_http_hello/core.dewy')


def host_target():
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
    system = {'darwin': 'mac', 'windows': 'windows'}.get(platform.system().lower(), 'linux')
    return f'{machine}-{system}'


def build(compiler, source, target, output, toolchain):
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update(DEWY_CORE_LIB=str(toolchain / 'lib'), DEWY_EMIT_WORKERS='1')
    return subprocess.run([compiler, 'build', source, '--target', target, '-o', output],
                          env=env, capture_output=True, text=True, timeout=180, check=False)


@pytest.fixture
def cross(compiler, request):
    target = request.param
    if target == host_target():
        pytest.skip(f'{target} is this host: the other suites build it')
    toolchain = compiler.parent.parent
    if not (toolchain / 'lib').is_dir():
        pytest.skip(f'{compiler} has no lib/ beside its bin/')
    return compiler, target, toolchain


@pytest.mark.parametrize('cross', TARGETS, indirect=True)
def test_compiler_builds_for_target(cross, tmp_path):
    compiler, target, toolchain = cross
    source = toolchain / 'compiler/main.jo'
    if not source.is_file():
        pytest.skip(f'{toolchain} has no compiler/ sources')
    built = build(compiler, source, target, tmp_path / 'dewy-core', toolchain)
    assert built.returncode == 0, f'compiler for {target}:\n{built.stdout}{built.stderr}'


@pytest.mark.parametrize('cross', TARGETS, indirect=True)
def test_target_branching_programs_build_for_target(cross, tmp_path):
    compiler, target, toolchain = cross
    failures = []
    for program in PROGRAMS:
        source = ROOT / program
        built = build(compiler, source, target, tmp_path / source.parent.name, toolchain)
        if built.returncode:
            failures.append(f'{program}:\n{built.stdout}{built.stderr}')
    assert not failures, f'for {target}:\n' + '\n'.join(failures)
