"""Measure complete compiler invocations in isolated artifact directories.

Each sample starts a fresh compiler process and rebuilds the executable. OS
page caches are not flushed. Hosted phase timings are observational wrappers;
the timed path is the ordinary CLI, with that revision's default build options.
This tool uses Python for measurement, not as part of the native build path.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def hosted_worker(argv: list[str]) -> int:
    sys.path.insert(0, os.environ.get('DEWY_BENCH_HOSTED_ROOT', str(ROOT)))
    from dewy import __main__ as cli
    from dewy.backend.udewy import emit, lower
    from dewy.semantic import check

    phases: dict[str, float] = {}

    def observe(owner, name, label):
        original = getattr(owner, name)

        def measured(*args, **kwargs):
            start = time.perf_counter()
            with Path('phase-events.jsonl').open('a') as events:
                events.write(json.dumps({'phase': label, 'event': 'start', 'time': start}) + '\n')
            try:
                return original(*args, **kwargs)
            finally:
                stop = time.perf_counter()
                phases[label] = phases.get(label, 0) + stop - start
                with Path('phase-events.jsonl').open('a') as events:
                    events.write(json.dumps({'phase': label, 'event': 'finish', 'time': stop}) + '\n')

        setattr(owner, name, measured)

    observe(check, 'typecheck_and_resolve', 'checking_seconds')
    observe(lower, 'lower_for_udewy', 'lowering_seconds')
    observe(emit, 'codegen_inner', 'lowering_and_emission_seconds')
    observe(cli, 'entry_point', 'backend_seconds')
    profiler = cProfile.Profile() if os.environ.get('DEWY_BENCH_PROFILE') else None
    try:
        if profiler:
            profiler.enable()
        return cli.run(argv)
    finally:
        if profiler:
            profiler.disable()
            profiler.dump_stats('hosted.prof')
        phases['emission_seconds'] = phases.get('lowering_and_emission_seconds', 0) - phases.get('lowering_seconds', 0)
        Path('phases.json').write_text(json.dumps(phases, indent=2) + '\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--native-executable', type=Path)
    parser.add_argument('--hosted-root', type=Path, default=ROOT,
                        help='pin the hosted packages and library to a source snapshot')
    parser.add_argument('--udewy-executable', type=Path)
    parser.add_argument('--library-root', type=Path,
                        help='pin library inputs independently of the benchmark driver')
    parser.add_argument('--target', choices=('x86_64', 'c'), default='x86_64')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--profile', action='store_true', help='hosted cProfile; timings include profiling overhead')
    args = parser.parse_args()
    if args.runs < 1 or args.timeout <= 0:
        parser.error('runs and timeout must be positive')
    if args.profile and args.native_executable:
        parser.error('--profile records hosted Python calls only')
    source = args.source.resolve(strict=True)
    hosted_root = args.hosted_root.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'results.jsonl').exists():
        parser.error('use a new output directory to preserve earlier measurements')
    env = os.environ | {'PYTHONPATH': str(ROOT), 'DEWY_LIBRARY_ROOT': str(ROOT / 'library')}
    if not args.native_executable:
        env |= {'PYTHONPATH': str(hosted_root), 'DEWY_LIBRARY_ROOT': str(hosted_root / 'library'),
                'DEWY_BENCH_HOSTED_ROOT': str(hosted_root)}
    if args.library_root:
        env['DEWY_LIBRARY_ROOT'] = str(args.library_root.resolve(strict=True))
    if args.udewy_executable:
        env['DEWY_UDEWY'] = str(args.udewy_executable.resolve(strict=True))
    if args.profile:
        env['DEWY_BENCH_PROFILE'] = '1'
    else:
        env.pop('DEWY_BENCH_PROFILE', None)
    compiler = [str(args.native_executable.resolve(strict=True))] if args.native_executable else [sys.executable, str(Path(__file__).resolve()), '--hosted-worker']
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    metadata = {
        'revision': revision,
        'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
        'platform': platform.platform(), 'machine': platform.machine(),
        'cpu': next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), None),
        'python': sys.version, 'compiler': compiler, 'target': args.target,
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'cache_state': 'fresh process and empty build directory; OS page caches uncontrolled',
        'profiled': args.profile,
        'toolchain': {name: subprocess.check_output([name, '--version'], text=True).splitlines()[0]
                      for name in ('cc', 'as', 'ld') if shutil.which(name)},
        'backend_environment': {key: value for key, value in env.items()
                                if key.startswith(('UDEWY_', 'DEWY_BOOTSTRAP_'))},
    }
    if args.native_executable:
        metadata['compiler_sha256'] = hashlib.sha256(args.native_executable.read_bytes()).hexdigest()
    else:
        metadata['hosted_root'] = str(hosted_root)
        digest = hashlib.sha256()
        for package in ('dewy', 'udewy', 'library'):
            for path in sorted((hosted_root / package).rglob('*')):
                if path.is_file() and path.suffix in ('.py', '.dewy', '.udewy'):
                    digest.update(str(path.relative_to(hosted_root)).encode() + b'\0')
                    digest.update(path.read_bytes())
        metadata['hosted_source_sha256'] = digest.hexdigest()
    if args.udewy_executable:
        metadata['udewy'] = str(args.udewy_executable.resolve())
        metadata['udewy_sha256'] = hashlib.sha256(args.udewy_executable.read_bytes()).hexdigest()
    library_root = Path(env['DEWY_LIBRARY_ROOT'])
    metadata['library_root'] = str(library_root)
    library_digest = hashlib.sha256()
    for path in sorted(library_root.rglob('*')):
        if path.is_file() and path.suffix in ('.dewy', '.udewy'):
            library_digest.update(str(path.relative_to(library_root)).encode() + b'\0')
            library_digest.update(path.read_bytes())
    metadata['library_sha256'] = library_digest.hexdigest()
    metadata['backend_driver'] = 'native executable' if args.native_executable else 'hosted in-process µDewy'
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    failed = False
    for run in range(args.runs):
        work = output / f'run-{run:02}'
        work.mkdir()
        command = ['/usr/bin/time', '-f', '%M', '-o', 'rss-kib.txt', *compiler, '--target', args.target, '-c', str(source)]
        started = time.perf_counter()
        with (work / 'stdout.log').open('w') as stdout, (work / 'stderr.log').open('w') as stderr:
            process = subprocess.Popen(command, cwd=work, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                status = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                status = 'timeout'
        record = {'run': run, 'status': status, 'wall_seconds': time.perf_counter() - started}
        rss = work / 'rss-kib.txt'
        if rss.exists() and rss.read_text().splitlines():
            last = rss.read_text().splitlines()[-1]
            if last.isdigit():
                record['max_process_rss_kib'] = int(last)
        phases = work / 'phases.json'
        if phases.exists():
            record.update(json.loads(phases.read_text()))
        record['udewy_artifacts'] = [
            {'path': str(path.relative_to(work)), 'bytes': path.stat().st_size,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(work.rglob('*.udewy'))
        ]
        with (output / 'results.jsonl').open('a') as results:
            results.write(json.dumps(record) + '\n')
        print(json.dumps(record), flush=True)
        failed |= status != 0
    return int(failed)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--hosted-worker']:
        raise SystemExit(hosted_worker(sys.argv[2:]))
    raise SystemExit(main())
