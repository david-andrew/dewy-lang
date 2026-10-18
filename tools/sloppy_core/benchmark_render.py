"""Compare fixed-step software rendering, retaining final frames for visual review."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import resource
import statistics
import struct
import subprocess
import time
from pathlib import Path

from tools.sloppy_core.benchmark_compile import ROOT, positive


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(compilers: dict[str, Path], games: list[str], artifacts: Path,
            samples: int, frames: int, threads: int) -> dict:
    artifacts.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_SOFTWARE='1', SLOPPY_WINDOW='1280x720', SLOPPY_FRAMES=str(frames),
               SLOPPY_FRAME_STATS='1', SLOPPY_THREADS=str(threads), SLOPPY_EMIT_WORKERS='1')
    report = {
        'platform': platform.platform(), 'samples': samples, 'warmups': 1,
        'last_frame_index': frames, 'threads': threads,
        'affinity': sorted(os.sched_getaffinity(0)), 'load_start': os.getloadavg(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'diff_sha256': hashlib.sha256(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT)).hexdigest(),
        'compilers': {label: {'path': str(path), 'sha256': digest(path),
                              'draw3d_sha256': digest(path.parent.parent / 'lib/game/draw3d.jo'),
                              'softgl_sha256': digest(path.parent.parent / 'lib/game/softgl.jo')}
                      for label, path in compilers.items()},
        'limits': [
            'Fresh release executables, fixed 1/60-second simulation steps, no interactive window or GPU.',
            'frame_ms is monotonic elapsed update/draw/submit time, despite the runtime label "frame cpu".',
            'process_cpu_seconds includes startup and PNG writing, and sums CPU time across threads.',
            'Shadow quality can differ; inspect retained images before accepting a speedup.',
        ],
        'workloads': {},
    }
    for game in games:
        source = ROOT / f'examples/sloppy_core/{game}.dewy'
        binaries, images = {}, {}
        for label, compiler in compilers.items():
            binaries[label] = artifacts / f'{game}-{label}'
            images[label] = artifacts / f'{game}-{label}.png'
            built = subprocess.run([compiler, 'build', source, '--release', '-o', binaries[label]],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=60, check=False)
            if built.returncode:
                raise RuntimeError(built.stdout + built.stderr)
        rows = {label: [] for label in compilers}
        labels = list(compilers)
        for sample in range(samples + 1):
            for label in labels if sample % 2 == 0 else labels[::-1]:
                run_env = {**env, 'SLOPPY_SCREENSHOT': str(images[label])}
                cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
                start = time.perf_counter()
                ran = subprocess.run([binaries[label]], cwd=ROOT, env=run_env,
                                     capture_output=True, text=True, timeout=60, check=False)
                wall = time.perf_counter() - start
                cpu1 = resource.getrusage(resource.RUSAGE_CHILDREN)
                match = re.search(r'frame cpu: ([\d.]+) ms average over (\d+) frames', ran.stderr)
                if ran.returncode or not match or int(match[2]) != frames + 1:
                    raise RuntimeError(f'{label} {game}: {ran.stdout}{ran.stderr}')
                png = images[label].read_bytes()
                if png[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', png[16:24]) != (1280, 720):
                    raise RuntimeError(f'{label} {game}: missing or wrongly sized image')
                if sample:
                    rows[label].append({
                        'frame_ms': float(match[1]), 'process_wall_seconds': wall,
                        'process_cpu_seconds': cpu1.ru_utime + cpu1.ru_stime - cpu0.ru_utime - cpu0.ru_stime,
                    })
        result = {'source_sha256': digest(source), 'samples': rows,
                  'images': {label: {'path': str(path), 'sha256': digest(path)} for label, path in images.items()}}
        if 'baseline' in rows:
            result['median_paired_candidate_baseline_ratio'] = {
                key: statistics.median(c[key] / b[key] for c, b in zip(rows['candidate'], rows['baseline']))
                for key in rows['candidate'][0]
            }
        report['workloads'][game] = result
        print(game, result.get('median_paired_candidate_baseline_ratio', rows), flush=True)
    report['load_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--baseline', type=Path)
    cli.add_argument('--game', choices=['paddle', 'forest', 'dunes'], action='append')
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--frames', type=positive, default=30)
    cli.add_argument('--threads', type=positive, default=2)
    cli.add_argument('--artifacts', type=Path, required=True)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    compilers = {}
    if args.baseline:
        compilers['baseline'] = args.baseline.resolve(strict=True)
    compilers['candidate'] = args.compiler.resolve(strict=True)
    report = measure(compilers, args.game or ['paddle', 'forest', 'dunes'],
                     args.artifacts.resolve(), args.samples, args.frames, args.threads)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
