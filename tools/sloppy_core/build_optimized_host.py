"""Build an optional C-optimized Linux x86-64 compiler from a native toolchain.

This is a release-toolchain step, not the compiler edit loop or a program backend.
The output is a separate immutable bundle; tools.core's cache is never replaced.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path

from tools.sloppy_core.build import identity
from tools.sloppy_core.c_host import translate
from tools.sloppy_core.performance_gate import toolchain_identity

HERE = Path(__file__).resolve().parent
FLAGS = ['-fno-strict-aliasing', '-ffp-contract=off',
         '-fno-stack-protector', '-fno-pie', '-fno-omit-frame-pointer',
         '-Werror=implicit-function-declaration', '-g1']


def job_limits():
    bound = 4 * 1024 ** 3
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    limit = min(bound, hard) if hard != resource.RLIM_INFINITY else bound
    if soft != resource.RLIM_INFINITY:
        limit = min(limit, soft)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_command(command, log: Path, timeout: float, *, env=None, expected_status: int = 0) -> dict:
    """Bound and reap one compiler or training process and its descendants."""
    before = time.monotonic()
    with log.open('w') as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                 env=env, preexec_fn=job_limits, start_new_session=True)
        try:
            status = child.wait(timeout=timeout)
            if status != expected_status:
                raise subprocess.CalledProcessError(status, command)
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise
    return {'command': [str(x) for x in command], 'seconds': time.monotonic() - before}


def compile_c(directory: Path, output: Path, cc: list[str], *, lto: bool = False,
              optimization: int = 2) -> dict:
    """Compile sequentially. Each C job has a time and address-space limit."""
    if optimization not in (2, 3):
        raise ValueError('Compiler-host optimization must be 2 or 3')
    manifest = json.loads((directory / 'manifest.json').read_text())
    steps = []
    objects = []
    started = time.monotonic()
    flags = [f'-O{optimization}', *FLAGS, *(['-flto=1'] if lto else [])]
    version = subprocess.check_output([*cc, '--version'], text=True).splitlines()[0]

    def run(command, log, timeout):
        steps.append(run_command(command, log, timeout))

    for name in [*manifest['units'], 'start.S']:
        src = directory / name
        obj = src.with_suffix('.o')
        run([*cc, *flags, '-c', src, '-o', obj], src.with_suffix('.log'), 120)
        objects.append(obj)
        print(f'{len(objects)}/{len(manifest["units"]) + 1} {name}', flush=True)
    run([*cc, *(flags if lto else []), '-nostartfiles', '-no-pie', *objects, '-lm', '-o', output],
        directory / 'link.log', 600 if lto else 30)
    return {'compiler': version, 'flags': flags, 'lto': lto, 'steps': steps,
            'seconds': time.monotonic() - started,
            'peak_child_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}


def build(toolchain: Path, output: Path, cc: list[str], *, lto: bool = False, pgo: bool = False,
          optimization: int | None = None) -> Path:
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('The optimized compiler-host build currently requires Linux x86-64')
    optimization = (3 if pgo else 2) if optimization is None else optimization
    if optimization not in (2, 3):
        raise ValueError('Compiler-host optimization must be 2 or 3')
    toolchain = toolchain.resolve(strict=True)
    seed = toolchain / 'bin/dewy-core'
    seed_identity = toolchain_identity(seed)
    # A native source-build manifest keeps this path explicit and non-recursive.
    source_build = json.loads((toolchain / 'build.json').read_text())
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ('compiler', 'lib'):
        shutil.copytree(toolchain / name, output / name)
    for name in ('LICENSE', 'NOTICE', 'UPSTREAM.json'):
        shutil.copy2(toolchain / name, output / name)
    (output / 'bin').mkdir()
    work = output / 'host-build'
    work.mkdir()
    ir = work / 'compiler.ir'
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_CORE_LIB=str(output / 'lib'), SLOPPY_EMIT_WORKERS='1')
    command = [seed, 'build', output / 'compiler/main.jo', '--host-ir', '--target', 'linux']
    with ir.open('w') as stdout, (work / 'export.log').open('w') as stderr:
        subprocess.run(command, env=env, stdout=stdout, stderr=stderr, check=True, timeout=120)
    translation = translate(ir, work / 'c')
    binary = output / 'bin/dewy-core'
    training_hashes = {}
    if pgo:
        from tools.sloppy_core.profiled_host import compiler_training, compile_profiled_c
        commands, training_hashes = compiler_training(output, work)
        result = compile_profiled_c(work / 'c', binary, cc, commands, env, lto=lto, optimization=optimization)
        translation['units'] = json.loads((work / 'c/manifest.json').read_text())['units']
        current_training = {str(p.relative_to(work)): identity(p)
                            for p in sorted((work / 'training-examples').rglob('*')) if p.is_file()}
        if current_training != training_hashes:
            raise ValueError('Training sources changed during the host build')
    else:
        result = compile_c(work / 'c', binary, cc, lto=lto, optimization=optimization)
    if toolchain_identity(seed) != seed_identity:
        raise ValueError('Native source toolchain changed during the host build')
    provenance = {
        'host': 'linux-x86_64', 'build_kind': 'scalar-C-optimized-host',
        'compiler_sha256': identity(binary), 'source_build': source_build,
        'native_seed': seed_identity, 'ir_sha256': identity(ir),
        'export_command': [str(x) for x in command],
        'translation': translation, 'c_build': result,
        'training_sources_sha256': training_hashes,
        'build_tools_sha256': {name: identity(HERE / name) for name in (
            'build_optimized_host.py', 'profiled_host.py', 'c_host.py', 'c_host_runtime.h', 'c_host_start.S', 'c_host_profile.c')},
        'generated_sources_sha256': {p.name: identity(p) for p in sorted((work / 'c').iterdir())
                                    if p.suffix in ('.c', '.h', '.S')},
    }
    (output / 'HOST_BUILD.json').write_text(json.dumps(provenance, indent=2) + '\n')
    toolchain_identity(binary)
    subprocess.run([binary, '--version'], env=env, check=True, timeout=10)
    return binary


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('toolchain', type=Path, help='native bundle built from the current compiler sources')
    cli.add_argument('--output', type=Path, required=True, help='new standalone bundle directory')
    cli.add_argument('--cc', default=os.environ.get('CC', 'gcc'), help='GCC-compatible C compiler command')
    cli.add_argument('--pgo', action='store_true', help='train GCC on representative builds, then optimize from fresh profiles (one worker)')
    cli.add_argument('--lto', action='store_true', help='also optimize across C units at link time (one worker)')
    cli.add_argument('--optimization', type=int, choices=(2, 3),
                     help='GCC optimization level (default: 3 with PGO, otherwise 2); training and final build use the same level')
    args = cli.parse_args()
    print(build(args.toolchain, args.output, shlex.split(args.cc), lto=args.lto, pgo=args.pgo,
                optimization=args.optimization))
