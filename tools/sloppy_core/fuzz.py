"""Bounded differential checks of Sloppy-generated programs on Dewy's shared backend.

This exercises the implementation-language frontend, optimizer and code generators;
it does not claim coverage of Dewy source parsing. No background work is scheduled.
Every build/run must succeed and print identical bytes in all requested modes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path

from tools.sloppy_core import fuzz_programs
from tools.sloppy_core.benchmark_compile import positive
from tools.sloppy_core.performance_gate import save_report, toolchain_identity

MAX_OUTPUT = 2 * 1024 * 1024
MAX_SOURCE = 256 * 1024


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'script':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def run(command: list, env: dict, timeout: float) -> dict:
    # Files avoid retaining arbitrarily large generated output in memory. A
    # timeout terminates only this command's process group, including emitters.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, env=env, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        status = 'complete'
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            status = 'timeout'
        stdout.seek(0)
        stderr.seek(0)
        out, err = stdout.read(MAX_OUTPUT + 1), stderr.read(MAX_OUTPUT + 1)
        if status == 'complete' and (len(out) > MAX_OUTPUT or len(err) > MAX_OUTPUT):
            status = 'output-limit'
        return {'status': status, 'returncode': process.returncode,
                'stdout': out, 'stderr': err}


def outcome(modes: dict[str, dict]) -> str:
    if not modes or any(v['status'] != 'complete' for v in modes.values()):
        return 'incomplete'
    if any(v['phase'] != 'run' or v['returncode'] != 0 for v in modes.values()):
        return 'execution-error'
    if len({v['stdout'] for v in modes.values()}) != 1:
        return 'mismatch'
    return 'pass'


def check(compiler: Path, output: Path, *, seed: int = 1, count: int = 25,
          wasm: bool = True, basic: bool = False, keep: bool = False) -> dict:
    if count < 1:
        raise ValueError('The program count must be positive')
    node = shutil.which('node') if wasm else None
    if wasm and not node:
        raise ValueError('Node is required for web checks; select --no-wasm explicitly to omit them')
    compiler = compiler.resolve(strict=True)
    identity = toolchain_identity(compiler)
    generator = Path(fuzz_programs.__file__)
    generator_hash = hashlib.sha256(generator.read_bytes()).hexdigest()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    modes = [('default', []), ('release', ['--release']), ('debug', ['-g'])]
    if wasm:
        modes += [('web', ['--target', 'wasm']), ('web-release', ['--target', 'wasm', '--release'])]
    report = {'status': 'incomplete', 'compiler': str(compiler), 'toolchain': identity,
              'generator_sha256': generator_hash, 'seed': seed, 'count': count,
              'basic': basic, 'modes': dict(modes), 'workers': 1,
              'node': {'path': node, 'version': subprocess.check_output([node, '--version'], text=True).strip()}
                      if node else None,
              'scope': 'Shared backend differential checks; no independent language-semantics oracle.',
              'results': []}
    destination = output / 'report.json'
    save_report(destination, report)
    started = time.monotonic()
    for number in range(seed, seed + count):
        case = output / f'seed-{number}'
        case.mkdir()
        gen = fuzz_programs.Gen(random.Random(number))
        if basic:
            gen.use_new = False
        source = gen.program().encode()
        path = case / 'program.jo'
        path.write_bytes(source)
        results = {}
        if len(source) <= MAX_SOURCE:
            for name, flags in modes:
                binary = case / name
                result = run([compiler, 'build', path, '-o', binary, *flags], env, 30)
                result['phase'] = 'build'
                if result['status'] == 'complete' and result['returncode'] == 0:
                    command = [binary]
                    if name.startswith('web'):
                        scripts = Scripts()
                        scripts.feed(binary.with_suffix('.html').read_text())
                        runner = binary.with_suffix('.cjs')
                        runner.write_text('\n'.join(scripts.parts))
                        command = [node, runner]
                    result = run(command, env, 10)
                    result['phase'] = 'run'
                results[name] = result
        status = outcome(results)
        summary = {'seed': number, 'status': status, 'source_bytes': len(source),
                   'source_sha256': hashlib.sha256(source).hexdigest(),
                   'vectors': gen.use_vec, 'extended': gen.use_new, 'modes': {}}
        for name, result in results.items():
            summary['modes'][name] = {k: v for k, v in result.items() if k not in ('stdout', 'stderr')}
            for stream in ('stdout', 'stderr'):
                data = result[stream]
                summary['modes'][name][stream + '_sha256'] = hashlib.sha256(data).hexdigest()
                summary['modes'][name][stream + '_bytes'] = len(data)
                if status != 'pass' or keep:
                    (case / (name + '.' + stream)).write_bytes(data)
        report['results'].append(summary)
        save_report(destination, report)
        print(f'seed {number}: {status}', flush=True)
        if status != 'pass':
            break  # Preserve the first failure and its executables for reduction.
        if not keep:
            shutil.rmtree(case)
    if identity != toolchain_identity(compiler) or generator_hash != hashlib.sha256(generator.read_bytes()).hexdigest():
        raise ValueError('Compiler or generator changed during fuzzing')
    report['status'] = 'pass' if len(report['results']) == count and all(
        r['status'] == 'pass' for r in report['results']) else 'failed'
    report['elapsed_seconds'] = time.monotonic() - started
    save_report(destination, report)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--compiler', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True, help='new directory; failed cases are retained')
    cli.add_argument('--count', type=positive, default=25)
    cli.add_argument('--seed', type=int, default=1)
    cli.add_argument('--no-wasm', action='store_true')
    cli.add_argument('--basic', action='store_true', help='omit union, stateful closure, SOA and matrix cases')
    cli.add_argument('--keep', action='store_true', help='retain successful sources, executables and output too')
    args = cli.parse_args()
    result = check(args.compiler, args.output, seed=args.seed, count=args.count,
                   wasm=not args.no_wasm, basic=args.basic, keep=args.keep)
    raise SystemExit(0 if result['status'] == 'pass' else 1)
