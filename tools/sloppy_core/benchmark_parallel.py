"""Compare serial and worker-pool particle simulation with identical value semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from tools.sloppy_core.benchmark_compile import positive

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'examples/sloppy_core/parallel_particles.dewy'


def measure(compiler: Path, count: int, steps: int, samples: int, threads: int) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(SLOPPY_EMIT_WORKERS='1', SLOPPY_THREADS=str(threads))
    report = {
        'compiler': str(compiler),
        'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
        'source_sha256': hashlib.sha256(MODEL.read_bytes()).hexdigest(),
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'count': count, 'steps': steps, 'samples': samples, 'threads_requested': threads,
        'cpu_affinity': sorted(os.sched_getaffinity(0)),
        'load_average_start': os.getloadavg(),
        'limits': ['Native release build; elapsed wall-clock kernel time.',
                   'Initialization and worker-pool warmup are outside the timed region.',
                   'Each simulation step allocates its next array, in both variants.',
                   'All-pairs particle forces are substantial independent work; tiny callbacks may be slower in parallel.',
                   'The OS may schedule other work on the same cores.'],
    }
    with tempfile.TemporaryDirectory(prefix='dewy-parallel-') as directory:
        work = Path(directory)
        (work / 'particles.dewy').write_bytes(MODEL.read_bytes())
        source = work / 'bench.dewy'
        source.write_text('''from p"particles.dewy" import make, advance
main=(args:array<string>)=>{
    let count=to_int(args[1]) ?? 512
    let steps=to_int(args[2]) ?? 8
    let parallel=args[3] =? "parallel"
    let initial=make(count)
    advance(initial 0.01 parallel);
    let state=initial
    let started=time_ns()
    loop i in [0..steps) {state=advance(state 0.01 parallel)}
    let elapsed=time_ns()-started
    let score=0.0
    loop i in [0..state.length) {
        let p=state[i]
        score+=(i+1)*(p.x+2*p.y+3*p.vx+5*p.vy)
    }
    printl"{score} {elapsed}"
    return 0
}
''')
        binary = work / 'bench'
        start = time.perf_counter()
        built = subprocess.run([compiler, 'build', source, '--release', '-o', binary], env=env,
                               capture_output=True, text=True, timeout=60, check=False)
        if built.returncode:
            raise RuntimeError(built.stdout + built.stderr)
        report['build_seconds'] = time.perf_counter() - start

        def execute(size, iterations, mode):
            result = subprocess.run([binary, str(size), str(iterations), mode], env=env,
                                    capture_output=True, text=True, timeout=60, check=False)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            score, ns = result.stdout.split()
            return score, int(ns)

        preflight = {}
        for size in (0, 1, 17, 128):
            serial, _ = execute(size, 3, 'serial')
            parallel, _ = execute(size, 3, 'parallel')
            if serial != parallel:
                raise RuntimeError(f'count={size}: unequal results {serial}, {parallel}')
            preflight[str(size)] = serial
        timings = {'serial': [], 'parallel': []}
        checksum = None
        for sample in range(samples + 1):
            order = ['serial', 'parallel'] if sample % 2 == 0 else ['parallel', 'serial']
            for mode in order:
                score, ns = execute(count, steps, mode)
                if checksum is None:
                    checksum = score
                if score != checksum:
                    raise RuntimeError(f'{mode}: unequal result {score}, expected {checksum}')
                if sample:
                    timings[mode].append(ns)
        report.update(
            preflight=preflight, checksum=checksum, nanoseconds=timings,
            median_ms={k: statistics.median(v) / 1e6 for k, v in timings.items()},
            paired_parallel_serial_ratio=statistics.median(
                p / s for s, p in zip(timings['serial'], timings['parallel'])),
        )
    report['load_average_end'] = os.getloadavg()
    print(report['median_ms'], flush=True)
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--count', type=positive, default=1024)
    cli.add_argument('--steps', type=positive, default=8)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--threads', type=positive, default=2)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    result = measure(args.compiler.resolve(strict=True), args.count, args.steps, args.samples, args.threads)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
