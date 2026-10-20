"""Compare graph discovery using lookup/insertion, one-probe insertion and reservation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from tools.compiler.benchmark_apps import (
    APPS,
    ROOT,
    digest,
    execute,
    prepare_clock,
    prepare_source,
    run,
)
from tools.compiler.benchmark_compile import positive


def variants(original: str) -> dict[str, str]:
    lookup = '''if distance.get(target) is? none {
                distance[target]=reached+1'''
    assert original.count(lookup) == 1, 'Graph discovery changed; update the benchmark adaptation'
    single = original.replace(lookup, 'if distance.insert_if_absent(target reached+1) {')
    setup = 'let queue:array<int64>=[label(0)]'
    assert single.count(setup) == 1, 'Graph setup changed; update the benchmark adaptation'
    reserved = single.replace(setup, 'distance.reserve(edges.length)\n    ' + setup
                              + '\n    queue.reserve(edges.length)')
    return {'original': original, 'insert-if-absent': single, 'reserved': reserved}


def measure(compiler: Path, count: int, samples: int, cc: str, clock: str = 'wall') -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    result = {
        'platform': platform.platform(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree': subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(
            ['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
        'compiler': {'path': str(compiler), 'sha256': digest(compiler)},
        'count': count, 'samples': samples, 'warmups_per_binary': 1,
        'kernel_clock': clock,
        'core_flags': ['--release'], 'c_flags': ['-O2'],
        'cc': run([cc, '--version'], env)[0],
        'load_average_start': os.getloadavg(),
        'limits': ['All Dewy variants use the same compiler and generated graph.',
                   'The reserved variant includes dictionary/queue reservation in kernel time.',
                   'C uses flat edges and a handwritten map; Dewy keeps ordered maps and per-node arrays.',
                   'Thread CPU timing excludes descheduling, but frequency and cache contention still matter.',
                   'These compare source/library usage, not compiler versions or frame rates.'],
    }
    manifest = compiler.parent.parent / 'build.json'
    if manifest.exists():
        result['compiler']['build_manifest'] = json.loads(manifest.read_text())
    result['harness_sha256'] = digest(ROOT / 'tools/compiler/benchmark_harness.jo')
    result['c_harness_sha256'] = digest(APPS / 'harness.h')
    with tempfile.TemporaryDirectory(prefix='dewy-map-benchmark-') as directory:
        work = Path(directory)
        original = prepare_source('graph', work).read_text()
        result['measured_harness_sha256'] = prepare_clock(work, clock)
        programs = variants(original)
        binaries, sources, builds = {}, {}, {}
        for name, text in programs.items():
            source = work / f'{name}.dewy'
            source.write_text(text)
            binaries[name] = work / name
            sources[name] = {'sha256': digest(source), 'source': text}
            _, builds[name] = run([compiler, 'build', source, '--release', '-o', binaries[name]], env)
        c_source = work / 'graph.c'
        shutil.copy2(APPS / 'graph.c', c_source)
        binaries['c'] = work / 'graph-c'
        _, builds['c'] = run([cc, '-O2', c_source, '-o', binaries['c']], env)
        checks = {}
        for size in [0, 1, 17, 1000]:
            actual = {name: execute(binary, size, env)[0] for name, binary in binaries.items()}
            if len(set(actual.values())) != 1:
                raise RuntimeError(f'count={size}: checksum mismatch {actual}')
            checks[str(size)] = actual['c']
        timings = {name: [] for name in binaries}
        labels = list(binaries)
        checksum = None
        for sample in range(samples + 1):
            for name in labels if sample % 2 == 0 else labels[::-1]:
                actual, timing = execute(binaries[name], count, env)
                if checksum is None:
                    checksum = actual
                if actual != checksum:
                    raise RuntimeError(f'{name}: expected {checksum}, got {actual}')
                if sample:
                    timings[name].append(timing)
        medians = {name: statistics.median(t['kernel_ns'] for t in rows) / 1e6
                   for name, rows in timings.items()}
        result.update(sources=sources, c_source_sha256=digest(c_source), build_seconds=builds,
                      binary_sha256={name: digest(path) for name, path in binaries.items()},
                      preflight_checksums=checks, checksum=checksum, timings=timings,
                      median_kernel_ms=medians, load_average_end=os.getloadavg())
        print(f'{clock} kernel: ' + ', '.join(f'{name}: {ms:.2f} ms' for name, ms in medians.items()), flush=True)
    return result


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--count', type=positive, default=1000000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--cc', default=shutil.which('cc') or 'cc')
    cli.add_argument('--clock', choices=['wall', 'thread-cpu'], default='wall')
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    report = measure(args.compiler.resolve(strict=True), args.count, args.samples, args.cc, args.clock)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
