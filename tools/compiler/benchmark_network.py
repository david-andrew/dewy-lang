"""Measure native idle-peer polling using inherited local sockets, without a server."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import statistics
import subprocess
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

from tools.compiler.benchmark_compile import ROOT, positive

SOURCE = '''import p"net.jo" as net
import p"clock.jo" as timer
main=(args:array<string>):>void=>{
    let polls=to_int(args[1]) ?? 0
    loop i in [2..args.length) {
        let fd=to_int(args[i]) ?? -1
        net.__net_peers.push(net.__NetPeer[id=i fd=fd state=2 client=true])
    }
    net.__net_poll()
    let started=timer.clock()
    loop _ in [0..polls) {net.__net_poll()}
    printl(timer.clock()-started)
    printl(net.__net_peers.length)
}
'''
CLOCK = '''clock = () -> int:
    ts: (int, int)
    syscall(228, 3, &ts)
    ts.0 * 1000000000 + ts.1
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(compiler: Path, libraries: dict[str, Path], peers: list[int],
            polls: int, samples: int) -> dict:
    if platform.system() != 'Linux':
        raise RuntimeError('The benchmark clock and inherited sockets require the Linux compiler host')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env['SLOPPY_EMIT_WORKERS'] = '1'
    report = {
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'compiler': str(compiler), 'compiler_sha256': digest(compiler),
        'harness_sha256': hashlib.sha256(SOURCE.encode()).hexdigest(),
        'clock_sha256': hashlib.sha256(CLOCK.encode()).hexdigest(),
        'library_sha256': {name: digest(path) for name, path in libraries.items()},
        'platform': platform.platform(), 'affinity': sorted(os.sched_getaffinity(0)),
        'samples': samples, 'polls': polls, 'warmups': 1,
        'clock': 'CLOCK_THREAD_CPUTIME_ID inside the polling loop',
        'limits': 'Idle native WebSocket transport polling only; no game frames, browser or WebRTC throughput claim.',
        'load_start': os.getloadavg(), 'results': {},
    }
    with tempfile.TemporaryDirectory(prefix='dewy-net-benchmark-') as temp:
        binaries = {}
        for label, library in libraries.items():
            folder = Path(temp) / label
            folder.mkdir()
            (folder / 'net.jo').write_bytes(library.read_bytes())
            (folder / 'clock.jo').write_text(CLOCK)
            source = folder / 'poll.dewy'
            source.write_text(SOURCE)
            binary = folder / 'poll'
            built = subprocess.run([compiler, 'build', source, '--release', '-o', binary],
                                   env=env, capture_output=True, text=True, timeout=30, check=False)
            if built.returncode:
                raise RuntimeError(built.stdout + built.stderr)
            binaries[label] = binary
        for count in peers:
            cpu, wall = ({label: [] for label in libraries} for _ in range(2))
            with ExitStack() as stack:
                descriptors = []
                for _ in range(count):
                    reader, writer = socket.socketpair()
                    stack.enter_context(reader)
                    stack.enter_context(writer)
                    reader.setblocking(False)
                    descriptors.append(reader.fileno())
                labels = list(libraries)
                for sample in range(samples + 1):
                    order = labels if sample % 2 == 0 else labels[::-1]
                    for label in order:
                        started = time.perf_counter()
                        ran = subprocess.run([binaries[label], str(polls), *map(str, descriptors)],
                                             pass_fds=descriptors, env=env, capture_output=True,
                                             text=True, timeout=60, check=False)
                        elapsed = time.perf_counter() - started
                        if ran.returncode:
                            raise RuntimeError(ran.stdout + ran.stderr)
                        ns, alive = map(int, ran.stdout.split())
                        if alive != count or ns <= 0:
                            raise RuntimeError(f'Unexpected polling result: {ran.stdout}')
                        if sample:
                            cpu[label].append(ns / 1e6)
                            wall[label].append(elapsed * 1000)
            medians = {label: statistics.median(values) for label, values in cpu.items()}
            row = {'cpu_ms': cpu, 'wall_ms': wall, 'median_cpu_ms': medians}
            if 'baseline' in cpu and 'candidate' in cpu:
                ratios = [c / b for b, c in zip(cpu['baseline'], cpu['candidate'], strict=True)]
                row['paired_cpu_ratios'] = ratios
                row['median_paired_cpu_ratio'] = statistics.median(ratios)
            report['results'][str(count)] = row
            print(f'{count} peers: {medians} ms CPU', flush=True)
    report['load_end'] = os.getloadavg()
    return report


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--net', type=Path, default=ROOT / 'lib/net.jo')
    cli.add_argument('--baseline-net', type=Path)
    cli.add_argument('--peers', type=positive, action='append')
    cli.add_argument('--polls', type=positive, default=10000)
    cli.add_argument('--samples', type=positive, default=7)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    sources = {}
    if args.baseline_net:
        sources['baseline'] = args.baseline_net.resolve(strict=True)
    sources['candidate'] = args.net.resolve(strict=True)
    result = measure(args.compiler.resolve(strict=True), sources, args.peers or [1, 8, 32],
                     args.polls, args.samples)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
