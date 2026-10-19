"""Compare Sloppy, the shared Jo path, and equivalent Dewy source on one core.

Snapshots binaries/libraries into task scratch; never writes to the Sloppy checkout.
The synthetic workload calls every generated function. Counts exclude libraries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tools.sloppy_core.benchmark_apps import prepare_clock, prepare_source
from tools.sloppy_core.benchmark_compile import ROOT, positive, sample_order


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(root: Path) -> dict:
    return {
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'status': subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
        'diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=root)).hexdigest(),
    }


def tree_digest(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            result.update(str(path.relative_to(root)).encode() + b'\0')
            result.update(bytes.fromhex(digest(path)))
    return result.hexdigest()


def generate_dewy(count: int) -> str:
    """Same algorithm and random constants as Sloppy's tools/genbench.py."""
    rng = random.Random(1)
    parts = ['Item:type=[x:float64 y:float64 id:int64]']
    for i in range(count):
        k = rng.randint(2, 9)
        parts.append(f'''work{i}=(a:int64 b:float64 items:array<Item>):>float64=>{{
    let total=0.0
    let count=0
    loop j in [0..a) {{
        let v=f64(j*{k})+b
        if v >? {k*10}.0 {{total+=v*0.5}}
        else if j%{k}=?0 {{total-=v/{k}.0}}
        else {{count+=1}}
    }}
    loop it in items {{
        if it.id%{k}=?1 {{total+=it.x*it.y}}
        else {{total+=sqrt(abs(it.x-it.y))}}
    }}
    let s="item {i}"
    if s.length >? {k} {{total+=f64(s.length)}}
    loop count >? {k} {{
        count-={k+1}
        total*=1.0001
    }}
    return total+f64(count)
}}''')
    parts.append('let items:array<Item>=[]\nloop i in [0..100) {items.push(Item[x=f64(i) y=f64(i)*0.5 id=i])}\nlet acc=0.0')
    parts.extend(f'acc+=work{i}({i%50} {i}.0 items)' for i in range(count))
    parts.append('printl"{acc}"')
    return '\n'.join(parts) + '\n'


def measure(dewy: Path, sloppy_root: Path, samples: int, functions: int,
            candidate: Path | None = None, shared_library: bool = True) -> dict:
    report = {
        'platform': platform.platform(),
        'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'method': 'Sequential fresh builds with rotating positions/directions, one emission worker, one discarded warmup; '
                  'warm filesystem caches. CPU = child user + system. Phase times are wall times. '
                  'Jo source is identical across compilers. Shared-library variants use Dewy library '
                  'snapshot because Dewy requires runtime helpers absent from Sloppy. '
                  'Source lines exclude libraries; the equivalent Dewy source has different formatting. '
                  'Compare time per workload, not only LOC/s. Libraries/binaries are snapshotted.',
        'samples': samples, 'generated_functions': functions,
        'include_sloppy_shared_library': shared_library,
        'dewy_checkout': identity(ROOT), 'sloppy_checkout': identity(sloppy_root),
        'compilers': {}, 'libraries': {}, 'workloads': {},
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    scratch = ROOT / '__dewycache__/task-tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sloppy-comparison-', dir=scratch) as temp:
        directory = Path(temp)
        libraries = {}
        for name, source in [('sloppy', sloppy_root / 'lib'), ('dewy', ROOT / 'core/lib')]:
            target = directory / f'{name}-lib'
            shutil.copytree(source, target)
            libraries[name] = target
            report['libraries'][name] = {'source': str(source), 'snapshot_sha256': tree_digest(target)}
        compilers = {}
        sources = {'sloppy': sloppy_root / 'bin/sloppy', 'dewy': dewy}
        if candidate:
            sources['candidate'] = candidate
        for name, source in sources.items():
            target = directory / name
            shutil.copy2(source, target)
            compilers[name] = target
            report['compilers'][name] = {'source': str(source), 'sha256': digest(target)}
        generator = sloppy_root / 'tools/genbench.py'
        report['sloppy_generator_sha256'] = digest(generator)
        subprocess.run([sys.executable, str(generator), str(functions), str(directory / 'big')], check=True)
        (directory / 'big.dewy').write_text(generate_dewy(functions))
        records = prepare_source('records', directory)
        prepare_clock(directory, 'thread-cpu')
        jo_records = directory / 'records.jo'
        jo_records.write_text((ROOT / 'dewy/benchmarks/apps/records.jo').read_text().replace(
            'time_ns()', 'bench_clock()') + '''\nbench_clock = () -> int:
    ts: (int, int)
    if syscall(228, 3, &ts) != 0: panic("thread clock unavailable")
    ts.0 * 1000000000 + ts.1
''')
        c_binary = directory / 'records-c'
        # Quoted C includes resolve beside the source first; copy it beside the clock-adapted header.
        shutil.copy2(ROOT / 'dewy/benchmarks/apps/records.c', directory / 'records.c')
        subprocess.run(['cc', '-O2', '-std=c11', '-D_POSIX_C_SOURCE=200809L',
                        str(directory / 'records.c'), '-o', str(c_binary)], check=True)
        for workload, jo_source, dewy_source in [('synthetic', directory / 'big.jo', directory / 'big.dewy'),
                                               ('records', jo_records, records)]:
            for mode in ['default', 'release']:
                variants = {'sloppy-own': ('sloppy', 'sloppy', jo_source),
                            'dewy-jo': ('dewy', 'dewy', jo_source),
                            'dewy-language': ('dewy', 'dewy', dewy_source)}
                if shared_library:
                    variants['sloppy-shared'] = ('sloppy', 'dewy', jo_source)
                if candidate:
                    variants.update({'candidate-jo': ('candidate', 'dewy', jo_source),
                                     'candidate-language': ('candidate', 'dewy', dewy_source)})
                rows = {name: [] for name in variants}
                outputs = {}
                for sample in range(samples + 1):
                    order = sample_order(list(variants), sample)
                    for name in order:
                        compiler, library, source = variants[name]
                        run_env = {**env, 'SLOPPY_LIB': str(libraries[library]),
                                   'DEWY_CORE_LIB': str(libraries[library])}
                        output = directory / f'{workload}-{mode}-{name}'
                        command = [str(compilers[compiler]), 'build', str(source), '--time', '-o', str(output)]
                        if mode == 'release':
                            command.append('--release')
                        before = resource.getrusage(resource.RUSAGE_CHILDREN)
                        start = time.perf_counter()
                        run = subprocess.run(command, env=run_env, capture_output=True, text=True, timeout=120, check=False)
                        wall = time.perf_counter() - start
                        after = resource.getrusage(resource.RUSAGE_CHILDREN)
                        if run.returncode:
                            raise RuntimeError(f'{name}: {run.stdout}{run.stderr}')
                        row = {'wall_seconds': wall,
                               'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                               'phases': run.stderr.strip()}
                        if sample:
                            rows[name].append(row)
                        outputs[name] = output
                data = {'variants': {name: {'compiler': compiler, 'library': library,
                                           'source_sha256': digest(source),
                                           'source_lines': len(source.read_text().splitlines()),
                                           'samples': rows[name],
                                           'median_cpu_seconds': statistics.median(r['cpu_seconds'] for r in rows[name]),
                                           'median_wall_seconds': statistics.median(r['wall_seconds'] for r in rows[name])}
                                     for name, (compiler, library, source) in variants.items()}}
                if workload == 'synthetic':
                    checksums = {name: float(subprocess.check_output([str(binary)], text=True, timeout=30))
                                 for name, binary in outputs.items()}
                    expected = checksums['sloppy-own']
                    assert all(math.isclose(expected, value, rel_tol=1e-10, abs_tol=0.001)
                               for value in checksums.values()), checksums
                    data['checksums'] = checksums
                else:
                    outputs['c'] = c_binary
                    runtime = {name: [] for name in outputs}
                    for count in [0, 1, 17, 1000]:
                        checksums = [int(subprocess.check_output([str(binary), str(count)], text=True).split()[0])
                                     for binary in outputs.values()]
                        assert len(set(checksums)) == 1, (count, checksums)
                    for sample in range(samples + 1):
                        order = sample_order(list(outputs), sample)
                        checksums = []
                        for name in order:
                            result = subprocess.check_output([str(outputs[name]), '1000000'], text=True, timeout=30)
                            checksum, ns = map(int, result.split())
                            checksums.append(checksum)
                            if sample:
                                runtime[name].append(ns)
                        assert len(set(checksums)) == 1, checksums
                    data['runtime'] = {'clock': 'CLOCK_THREAD_CPUTIME_ID', 'count': 1000000,
                                       'checksum': checksums[0], 'kernel_ns': runtime,
                                       'median_kernel_ns': {name: statistics.median(values)
                                                            for name, values in runtime.items()}}
                report['workloads'][f'{workload}-{mode}'] = data
                print(f'{workload}-{mode}: ' + ', '.join(
                    f'{name} {values["median_cpu_seconds"]*1000:.1f} ms CPU'
                    for name, values in data['variants'].items()), flush=True)
                if 'runtime' in data:
                    print('  runtime: ' + ', '.join(f'{name} {value/1e6:.1f} ms'
                                                  for name, value in data['runtime']['median_kernel_ns'].items()), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dewy', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--sloppy-root', type=Path, required=True)
    parser.add_argument('--samples', type=positive, default=5)
    parser.add_argument('--functions', type=positive, default=2000)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-shared-library', action='store_true',
                        help='omit the cross-library variant when upstream runtime APIs have diverged')
    args = parser.parse_args()
    result = measure(args.dewy.resolve(strict=True), args.sloppy_root.resolve(strict=True),
                     args.samples, args.functions, args.candidate.resolve(strict=True) if args.candidate else None,
                     shared_library=not args.no_shared_library)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
