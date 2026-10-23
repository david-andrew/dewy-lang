"""Pinned cycle companion to the instruction gate (see speed --help)."""
import os
import statistics
import subprocess

from tools.compiler import speed
from tools.filelock import lock_exclusive


def run(counter, command, env, cpu, metric):
    options = ['--cycles'] if metric == 'cycles' else []
    result = subprocess.run(['taskset', '-c', str(cpu), counter.binary, *options, *command],
                            cwd=speed.ROOT, env=env, capture_output=True, text=True)
    if result.returncode:
        raise speed.CompileError(result.stdout + result.stderr)
    return speed.counter_result(result.stderr, metric)


def report(args, current):
    speed.CACHE.mkdir(parents=True, exist_ok=True)
    with (speed.CACHE / 'speed.lock').open('w') as lock:
        lock_exclusive(lock)
        counter = speed.Counter('perf')
        commit = speed.resolve(args.base)
        base, _ = speed.base_compiler(commit, current)
        hosts = {'base': speed.Toolchain(commit[:10], base / 'bin/dewy-core', base / 'lib'),
                 'candidate': speed.Toolchain('candidate', speed.candidate_compiler(current), speed.ROOT / 'lib')}
        print(f'compile cycles: base {commit[:10]}, candidate working tree; CPU {args.cpu}; '
              f'{args.runs} interleaved runs, 1 emission worker; load {os.getloadavg()}', flush=True)
        failed = False
        for name, source, flags in speed.panel(args.release):
            samples = {role: [] for role in hosts}
            instructions = {}

            def once(role, metric):
                active = speed.stage(hosts[role])
                command = [active / 'bin/dewy-core', 'build', speed.ROOT / source, *flags,
                           '-o', speed.CACHE / 'panel/program']
                env = speed.clean_env(DEWY_CORE_LIB=str(active / 'lib'))
                return run(counter, command, env, args.cpu, metric)

            # Same source and active path for both hosts; a compile failure is fatal.
            for role in hosts:
                once(role, 'cycles')
                instructions[role] = once(role, 'instructions')
            for k in range(args.runs):
                for role in (list(hosts) if k % 2 == 0 else list(hosts)[::-1]):
                    samples[role].append(once(role, 'cycles'))
            med = {role: statistics.median(values) for role, values in samples.items()}
            change = speed.delta(med['base'], med['candidate'])
            over = args.limit is not None and change > args.limit
            failed |= over
            print(f'  {name:26} cycles {med["base"] / 1e9:.4f} -> {med["candidate"] / 1e9:.4f} G '
                  f'{change:+.2f}%; instructions {speed.delta(instructions["base"], instructions["candidate"]):+.2f}%'
                  + (' <-' if over else ''), flush=True)
            print('    cycle ranges G: ' + ', '.join(
                f'{role} {min(values) / 1e9:.4f}..{max(values) / 1e9:.4f}' for role, values in samples.items()), flush=True)
        print(f'  load after {os.getloadavg()}', flush=True)
        return int(failed)
