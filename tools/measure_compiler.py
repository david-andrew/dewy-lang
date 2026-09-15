"""Measure complete compiler invocations in isolated artifact directories.

Each sample starts a fresh compiler process and rebuilds the executable. Warm
samples first prime the analysis caches, then remove the executable. OS
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
import gc
import time

ROOT = Path(__file__).resolve().parents[1]


def native_observations(stderr: str) -> dict:
    """Read optional native phase counters without treating diagnostics as data."""
    timings: dict[str, int] = {}
    storage: dict[str, dict[str, int]] = {}
    for line in stderr.splitlines():
        fields = line.split()
        if (len(fields) == 5 and fields[:2] == ['dewy', 'timing']
                and fields[4] == 'ns' and fields[3].isdigit()):
            timings[fields[2]] = timings.get(fields[2], 0) + int(fields[3])
        elif len(fields) == 7 and fields[:2] == ['dewy', 'storage']:
            try:
                counters = dict(field.split('=') for field in fields[3:])
                if set(counters) != {'allocated', 'copied', 'live', 'peak'}:
                    continue
                values = {key: int(value) for key, value in counters.items()}
            except ValueError:
                continue
            if any(value < 0 for value in values.values()):
                continue
            previous = storage.get(fields[2])
            if previous is not None:
                values['allocated'] += previous['allocated']
                values['copied'] += previous['copied']
                values['peak'] = max(values['peak'], previous['peak'])
            storage[fields[2]] = values
    result = {'reported_phase_nanoseconds': timings}
    if storage:
        result['reported_phase_arena_bytes'] = storage
    return result


def hosted_worker(argv: list[str]) -> int:
    sys.path.insert(0, os.environ.get('DEWY_BENCH_HOSTED_ROOT', str(ROOT)))
    from dewy import __main__ as cli
    from dewy.backend.udewy import direct, emit, lower
    from dewy.semantic import check
    from udewy import frontend, t0

    phases: dict[str, float] = {}
    active_phases: list[str] = []
    collections: dict[str, dict] = {}
    collection_started: dict[int, tuple[float, str]] = {}

    def observe_collection(event, info):
        generation = info['generation']
        if event == 'start':
            collection_started[generation] = (
                time.perf_counter(), active_phases[-1] if active_phases else 'outside_phases')
        elif event == 'stop' and generation in collection_started:
            start, phase = collection_started.pop(generation)
            row = collections.setdefault(phase, {'seconds': 0.0, 'collections': 0,
                                                'collected': 0, 'uncollectable': 0})
            row['seconds'] += time.perf_counter() - start
            row['collections'] += 1
            row['collected'] += info['collected']
            row['uncollectable'] += info['uncollectable']

    def observe(owner, name, label):
        original = getattr(owner, name)

        def measured(*args, **kwargs):
            start = time.perf_counter()
            with Path('phase-events.jsonl').open('a') as events:
                events.write(json.dumps({'phase': label, 'event': 'start', 'time': start}) + '\n')
            active_phases.append(label)
            try:
                return original(*args, **kwargs)
            finally:
                stop = time.perf_counter()
                active_phases.pop()
                phases[label] = phases.get(label, 0) + stop - start
                with Path('phase-events.jsonl').open('a') as events:
                    events.write(json.dumps({'phase': label, 'event': 'finish', 'time': stop}) + '\n')

        setattr(owner, name, measured)

    observe(check, 'typecheck_and_resolve', 'checking_seconds')
    observe(lower, 'lower_for_udewy', 'lowering_seconds')
    observe(emit, '_emit_program', 'emission_seconds')
    observe(cli, 'entry_point', 'backend_seconds')
    # Nested backend phases explain where the complete backend time goes.
    # Keep the aggregate for comparisons with earlier campaign samples.
    observe(t0, 'load_program', 'source_loading_seconds')
    observe(direct, 'compile_program', 'code_generation_seconds')
    original_backend = frontend.get_backend

    def measured_backend(name):
        backend = original_backend(name)
        observe(backend, 'compile_and_link', 'toolchain_seconds')
        return backend

    frontend.get_backend = measured_backend
    profiler = cProfile.Profile() if os.environ.get('DEWY_BENCH_PROFILE') else None
    gc.callbacks.append(observe_collection)
    try:
        if profiler:
            profiler.enable()
        return cli.run(argv)
    finally:
        gc.callbacks.remove(observe_collection)
        Path('garbage-collection.json').write_text(json.dumps(collections, indent=2) + '\n')
        if profiler:
            profiler.disable()
            profiler.dump_stats('hosted.prof')
        Path('phases.json').write_text(json.dumps(phases, indent=2) + '\n')


def invocation(command, work: Path, env: dict[str, str], timeout: float, *, profile: bool, prefix: str = '') -> dict:
    """Run one fresh process; a priming run uses the same timeout policy."""
    started = time.perf_counter()
    with (work / f'{prefix}stdout.log').open('w') as stdout, (work / f'{prefix}stderr.log').open('w') as stderr:
        process = subprocess.Popen(command, cwd=work, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # A profiled worker can save partial data. It remains a timeout,
            # even if interruption unwinds successfully.
            os.killpg(process.pid, signal.SIGINT if profile else signal.SIGKILL)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            status = 'timeout'
    return {'status': status, 'wall_seconds': time.perf_counter() - started}


def prepare_warm_rebuild(source: Path, work: Path) -> None:
    """Retain analysis caches, but require another executable build.

    Both compiler commands use the shared artifact layout. Removing the
    executable prevents the hosted CLI's mtime shortcut; source, parse and
    checked-prelude caches stay intact. The work directory belongs to this
    measurement, never to the user's source checkout.
    """
    sys.path.insert(0, str(ROOT))
    from udewy.cache import cache_artifact
    binary = work / cache_artifact(source, cwd=work)
    if not binary.is_file():
        raise RuntimeError(f'priming succeeded without the expected executable: {binary}')
    binary.unlink()
    # Preserve priming observations separately. None may leak into the
    # measured run (notably append-only phase events).
    prime = work / 'priming'
    prime.mkdir()
    for name in ('rss-kib.txt', 'phases.json', 'garbage-collection.json', 'phase-events.jsonl', 'hosted.prof'):
        observation = work / name
        if observation.exists():
            observation.rename(prime / name)


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
    parser.add_argument('--cache-state', choices=('cold', 'warm'), default='cold',
                        help='warm primes the analysis caches, then removes the executable before timing a full rebuild')
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--profile', action='store_true', help='hosted cProfile; timings include profiling overhead')
    parser.add_argument('--phase-timings', action='store_true', help='request --timings from a compiler that supports it')
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
        'python_jit': {
            'available': hasattr(sys, '_jit') and sys._jit.is_available(),
            'enabled': hasattr(sys, '_jit') and sys._jit.is_enabled(),
        },
        'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'cache_state': ('fresh process and empty build directory' if args.cache_state == 'cold' else
                        'fresh process after a priming build; analysis caches retained, executable removed') + '; OS page caches uncontrolled',
        'cache_mode': args.cache_state,
        'profiled': args.profile, 'phase_timings': args.phase_timings,
        'toolchain': {name: subprocess.check_output([name, '--version'], text=True).splitlines()[0]
                      for name in ('cc', 'as', 'ld') if shutil.which(name)},
        'backend_environment': {key: value for key, value in env.items()
                                if key.startswith(('UDEWY_', 'DEWY_BOOTSTRAP_'))},
        'analysis_environment': {key: env[key] for key in
                                 ('DEWY_NO_PRELUDE_CACHE', 'DEWY_NO_RESIDENT_PRELUDE', 'PYTHON_JIT')
                                 if key in env},
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
        command = ['/usr/bin/time', '-f', '%M', '-o', 'rss-kib.txt', *compiler,
                   *(['--timings'] if args.phase_timings else []), '--target', args.target, '-c', str(source)]
        priming = None
        if args.cache_state == 'warm':
            priming = invocation(command, work, env, args.timeout, profile=args.profile, prefix='priming-')
            if priming['status'] != 0:
                record = {'run': run, 'status': 'priming_failed', 'priming': priming}
                with (output / 'results.jsonl').open('a') as results:
                    results.write(json.dumps(record) + '\n')
                print(json.dumps(record), flush=True)
                failed = True
                continue
            prepare_warm_rebuild(source, work)
        record = {'run': run, **invocation(command, work, env, args.timeout, profile=args.profile)}
        status = record['status']
        if priming is not None:
            record['priming'] = priming
        rss = work / 'rss-kib.txt'
        if rss.exists() and rss.read_text().splitlines():
            last = rss.read_text().splitlines()[-1]
            if last.isdigit():
                record['max_process_rss_kib'] = int(last)
        phases = work / 'phases.json'
        if phases.exists():
            record.update(json.loads(phases.read_text()))
        collection_report = work / 'garbage-collection.json'
        if collection_report.is_file():
            record['garbage_collection'] = json.loads(collection_report.read_text())
        if args.phase_timings:
            record.update(native_observations((work / 'stderr.log').read_text()))
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
