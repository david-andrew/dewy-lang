#!/usr/bin/env python3
"""Diagnostic runtime copies: counters and controlled scheduler ablations.

Never time the instrumented binaries as a performance gate. No counter, switch,
or environment lookup is added to the shipping runtime. Each source edit below
must match exactly once, so runtime changes cannot silently invalidate a probe.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys

from run import ROOT, SIZES, SMALL, physical_cpus, selected_cpus, count_pinned

FIELDS = ('forks', 'joins', 'ticks', 'clock_reads', 'promotions', 'steals',
          'serial_frontiers', 'range_leaves', 'serial_jobs', 'serial_items')


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f'diagnostic runtime hook changed: {old!r}')
    return source.replace(old, new, 1)


def runtime_source(source: str, *, counters=False, mode='normal', depth=8) -> str:
    source = replace_once(source, '[36] < 8', f'[36] < {depth}')
    if mode == 'no-promotion':
        start = source.index('__fj_tick = (q: *int):')
        end = source.index('\n@noinline\n__fj_link', start)
        source = source[:start] + '__fj_tick = (q: *int):\n    return\n' + source[end:]
    if not counters:
        return source
    hooks = {
        '__fj_link = (j: *int):': '    __fj_dbg_add(0, 1)',
        '__fj_join = (j: *int):': '    __fj_dbg_add(1, 1)',
        '__fj_tick = (q: *int):': '    __fj_dbg_add(2, 1)',
        '    if hi - lo <= 1:': '        __fj_dbg_add(7, 1)',
    }
    for hook, line in hooks.items():
        source = replace_once(source, hook + '\n', hook + '\n' + line + '\n')
    source = replace_once(source, '    __fj_workers = 0\n',
                          '    __fj_dbg = __os_pages((__MAX_THREADS + 1) * 128) as *int\n    __fj_workers = 0\n')
    source = replace_once(source, '        if j != null: return j',
                          '        if j != null:\n            __fj_dbg_add(5, 1)\n            return j')
    source = replace_once(source, f'    (__fj_deques + __tid() * __fj_WORDS)[36] < {depth}',
                          f'    split = (__fj_deques + __tid() * __fj_WORDS)[36] < {depth}\n'
                          '    if not split: __fj_dbg_add(6, 1)\n    split')
    source = replace_once(source, '    else: __call_raw(j[5] as *u8, null, j as *u8)',
                          '    else:\n        __fj_dbg_add(8, 1)\n        __fj_dbg_add(9, j[3] - j[2])\n'
                          '        __call_raw(j[5] as *u8, null, j as *u8)')
    if mode != 'no-promotion':
        source = replace_once(source, '    now = time_ns()', '    __fj_dbg_add(3, 1)\n    now = time_ns()')
        source = replace_once(source, '    j[7] = 1', '    __fj_dbg_add(4, 1)\n    j[7] = 1')
    source += '''
# Debug overlay only. One padded row per owner; no atomic hot-path counters.
__fj_dbg: *int = null
__fj_dbg_add = (field: int, count: int):
    p = __fj_dbg + __tid() * 16 + field
    p[0] += count
__fj_dbg_report = ():
    if __fj_dbg == null: return
    loop id in [0..__fj_workers + 1):
        p = __fj_dbg + id * 16
        eprint("FJ_STATS {id} {p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {p[5]} {p[6]} {p[7]} {p[8]} {p[9]}")
'''
    return source


def stage(work: Path, label: str, *, counters=False, mode='normal', depth=8) -> Path:
    directory = work / label
    lib = directory / 'lib'
    shutil.copytree(ROOT / 'lib', lib, dirs_exist_ok=True)
    runtime = lib / 'std/fork_join.jo'
    runtime.write_text(runtime_source(runtime.read_text(), counters=counters, mode=mode, depth=depth))
    bench = directory / 'bench'
    (bench / 'parallel').mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'examples', directory / 'examples', dirs_exist_ok=True)
    harness = (ROOT / 'bench/harness.jo').read_text()
    if counters:
        harness += '\nforkjoin_report = (): __fj_dbg_report()\n'
    (bench / 'harness.jo').write_text(harness)
    for name in SIZES:
        source = (ROOT / 'bench/parallel' / f'{name}.dewy').read_text()
        if counters:
            source = replace_once(source, 'import clock, size_argument', 'import clock, size_argument, forkjoin_report')
            at = source.rindex('}')
            source = source[:at] + '    forkjoin_report()\n' + source[at:]
        (bench / 'parallel' / f'{name}.dewy').write_text(source)
    return directory


def parse_stats(stderr: str) -> dict:
    lanes = {}
    for line in stderr.splitlines():
        if line.startswith('FJ_STATS '):
            lane, *values = map(int, line.split()[1:])
            if len(values) != len(FIELDS) or lane in lanes:
                raise ValueError(f'invalid counter row: {line}')
            lanes[lane] = dict(zip(FIELDS, values))
    if not lanes:
        raise ValueError('missing debug runtime counters')
    totals = {field: sum(row[field] for row in lanes.values()) for field in FIELDS}
    if totals['forks'] != totals['joins']:
        raise ValueError('unbalanced fork/join counters')
    return {'lanes': lanes, 'total': totals}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--kernels', nargs='+', choices=SIZES, default=list(SIZES))
    parser.add_argument('--workers', nargs='+', type=int, default=[1, 2, 4])
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--depths', nargs='+', type=int, default=[8])
    parser.add_argument('--small', action='store_true')
    parser.add_argument('--allow-smt', action='store_true')
    parser.add_argument('--counters-only', action='store_true', help='skip instruction-count ablations')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    cpus = selected_cpus(args.allow_smt)
    if args.runs < 1 or any(n < 1 or n > min(4, len(cpus)) for n in args.workers):
        parser.error('positive runs and 1–4 available CPUs required (SMT needs --allow-smt)')
    if any(n < 1 or n > 32 for n in args.depths):
        parser.error('frontier depths must be between 1 and 32')
    sys.path.insert(0, str(ROOT))
    from tools.compiler.speed import CACHE, Counter
    CACHE.mkdir(parents=True, exist_ok=True)
    counter = None if args.counters_only else Counter('auto')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'OMP_'))}
    env['DEWY_EMIT_WORKERS'] = '1'
    args.work = args.work.resolve()
    args.work.mkdir(parents=True, exist_ok=True)
    compiler = args.compiler.resolve()
    report = {'counter': counter.label if counter else None, 'kernels': {},
              'physical_cpus': physical_cpus(), 'selected_cpus': cpus,
              'uses_smt': max(args.workers) > len(physical_cpus()), 'note':
              'Whole-process instructions. Debug counters are separate runs and perturb heartbeat timing. '
              'No-promotion retains fork/join and allocator sharing. '
              'Differences are controlled ablations, not additive attribution.'}
    variants = []
    for depth in args.depths:
        for mode in ('normal', 'no-promotion'):
            for debug in (False, True):
                if args.counters_only and not debug:
                    continue
                variants.append((f'{mode}-d{depth}' + ('-stats' if debug else ''), debug, mode, depth))
    staged = {label: stage(args.work, label, counters=debug, mode=mode, depth=depth)
              for label, debug, mode, depth in variants}
    for kernel in args.kernels:
        rows = {}
        expected = None
        size = (SMALL if args.small else SIZES)[kernel]
        for label, debug, mode, depth in variants:
            directory = staged[label]
            binary = directory / kernel
            build_env = dict(env, DEWY_CORE_LIB=str(directory / 'lib'))
            subprocess.run([compiler, 'build', directory / 'bench/parallel' / f'{kernel}.dewy',
                            '--release', '-o', binary], env=build_env, check=True, timeout=120)
            rows[label] = {}
            for workers in args.workers:
                command = [shutil.which('taskset'), '-c', ','.join(map(str, cpus[:workers])), str(binary), str(size)]
                run_env = dict(env, DEWY_THREADS=str(workers))
                readings = []
                for repeat in range(args.runs):
                    if debug:
                        result = subprocess.run(command, env=run_env, capture_output=True, text=True,
                                                check=True, timeout=120)
                        output = result.stdout
                        readings.append(parse_stats(result.stderr))
                    else:
                        instructions, output = count_pinned(counter, command[3:], run_env, cpus[:workers])
                        readings.append(instructions)
                    checksum = int(output.split()[0])
                    if expected is None:
                        expected = checksum
                    if checksum != expected:
                        raise RuntimeError(f'{kernel}/{label}/{workers}: checksum {checksum} != {expected}')
                rows[label][workers] = readings
                summary = [r['total'] for r in readings] if debug else int(statistics.median(readings))
                print(f'{kernel} {label} {workers}: {summary}', flush=True)
        report['kernels'][kernel] = {'size': size, 'checksum': expected, 'variants': rows}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
