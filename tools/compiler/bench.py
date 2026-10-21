"""Quick look at runtime speed: the bench/ kernels in Dewy (default and release
builds) against their C counterparts (cc -O2).

Prints the median kernel time of a few runs, the Dewy/C ratios and whether every
build printed the same checksum. Wall-clock timing on a shared machine is noisy;
this is a quick look, not a gate.

--instructions counts each Dewy build's user-space instructions instead (the
whole run, setup included), with the counter `speed` uses. --baseline REV also
builds REV's compiler as `speed` does (cached) and fails when any kernel and
mode needs more than --limit percent (default 3) more instructions than REV's
build, or prints another checksum.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / 'bench'
SCRATCH = ROOT / '__dewycache__' / 'bench'
# Input size per kernel (roughly 5-400 ms each in C).
COUNTS = {'callbacks': 1000000, 'game': 5000000, 'helpers': 500000, 'arrays': 10000000, 'records': 1000000, 'records_nested': 1000000,
          'text': 10000000, 'graph': 1000000, 'string_equal': 10000000, 'match_dispatch': 10000000,
          'branch_dispatch': 10000000, 'managed_params': 10000000, 'method_params': 10000000,
          'shifted_arrays': 100000, 'case_conversion': 20000, 'array_swap': 10000000,
          'integer_parse': 2000000, 'recursive_list': 20000, 'recursive_tree': 2000000}
MODES = ('default', 'release')
# Kernels without their own C file share another's algorithm and checksum.
C_SOURCE = {'records_nested': 'records'}
# Checksums at size 1000, for the correctness suite.
CHECKSUMS_1000 = {'callbacks': 155768, 'game': 2096, 'helpers': 985290002, 'arrays': 876830114, 'records': 649125068,
                  'text': 681360428, 'graph': 740553269, 'string_equal': 171284, 'match_dispatch': 29443,
                  'branch_dispatch': 517766884, 'managed_params': 250508, 'method_params': 250508,
                  'shifted_arrays': 2100736000, 'case_conversion': 17080000, 'array_swap': 888753138,
                  'integer_parse': 33285884}


def prepare_source(name: str, directory: Path) -> Path:
    """Swap the raw-syscall harness for bench/harness.jo and the old `:addr` index spelling."""
    source = directory / f'{name}.dewy'
    source.write_text((BENCH / f'{name}.dewy').read_text()
                      .replace('p"harness.dewy"', 'p"harness.jo"')
                      .replace(':addr', ':int64'))
    shutil.copy2(BENCH / 'harness.jo', directory)
    return source


def selected(words: str | None) -> list[str]:
    if not words:
        return list(COUNTS)
    terms = words.replace(',', ' ').split()
    return [name for name in COUNTS if any(term in name for term in terms)]


def run(command: list, count: int) -> tuple[int, int]:
    result = subprocess.run([*command, str(count)], capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed:\n{result.stdout}{result.stderr}')
    checksum, nanoseconds = map(int, result.stdout.split())
    return checksum, nanoseconds


def build(compiler: Path, source: Path, mode: str, output: Path, env: dict) -> str | None:
    """Build a kernel; the compiler's complaint when it cannot."""
    built = subprocess.run([compiler, 'build', source, *(['--release'] if mode == 'release' else []),
                            '-o', output], env=env, capture_output=True, text=True, timeout=300)
    return f'{built.stdout}{built.stderr}' if built.returncode else None


def compare(item: str, counts: list[int], checksums: list[str], limit: float) -> tuple[float, list[str]]:
    """The change from base to new in percent, and what fails: more than limit, or another checksum."""
    from tools.compiler.speed import delta

    change = round(delta(counts[0], counts[1]), 2) + 0.0
    failures = []
    if change > limit:
        failures.append(f'{item} needs {change:+.2f}% instructions (limit {limit}%)')
    if checksums[0] != checksums[1]:
        failures.append(f'{item} prints checksum {checksums[1]}, base {checksums[0]}')
    return change, failures


def instructions(args, names: list[str], compiler: Path) -> int:
    from tools.compiler import speed

    speed.CACHE.mkdir(parents=True, exist_ok=True)
    counter = speed.Counter(args.counter)
    toolchains = [('new', compiler, ROOT / 'lib')]
    if args.baseline:
        commit = speed.resolve(args.baseline)
        with (speed.CACHE / 'speed.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            directory, built = speed.base_compiler(commit, compiler)
        if built:
            print(f'(built base compiler {commit[:10]})', file=sys.stderr, flush=True)
        toolchains.insert(0, (f'base {commit[:10]}', directory / 'bin/dewy-core', directory / 'lib'))
    # (cachegrind runs ~50x slower: smaller inputs, the same comparison)
    scale = 1 if counter.kind == 'perf' else 10
    print(f'runtime instructions, M ({counter.label}' + (', inputs / 10' if scale > 1 else '') + '): '
          + (f'{args.baseline} ({commit[:10]}) -> ' if args.baseline else '') + 'this checkout', flush=True)
    print((f'{"kernel":16} ' + ''.join(f'{mode:>34}  ' if args.baseline else f'{mode:>12}' for mode in MODES)).rstrip(),
          flush=True)
    failures, notes = [], []
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bench-', dir=SCRATCH) as temporary:
        work = Path(temporary)
        for name in names:
            source = prepare_source(name, work)
            line = f'{name:16} '
            for mode in MODES:
                counts, checksums = [], []
                for label, binary, lib in toolchains:
                    env = speed.clean_env(DEWY_CORE_LIB=str(lib))
                    output = work / f'{name}-{mode}-{len(counts)}'
                    error = build(binary, source, mode, output, env)
                    if error is not None:
                        if label == 'new':
                            raise RuntimeError(f'{name} ({mode}) failed to build:\n{error}')
                        notes.append(f'{label} cannot build {name} ({mode}): not compared')
                        break
                    count, stdout = counter.run([output, str(COUNTS[name] // scale)], env)
                    counts.append(count)
                    checksums.append(stdout.split()[0])
                if len(counts) < len(toolchains):
                    line += f'{"(not compared)":>34}  '
                    continue
                if not args.baseline:
                    line += f'{counts[0] / 1e6:12.1f}'
                    continue
                change, found = compare(f'{name} ({mode})', counts, checksums, args.limit)
                failures += found
                line += (f'{counts[0] / 1e6:12.1f} -> {counts[1] / 1e6:10.1f} {change:+6.2f}%'
                         + (' <' if found else '  '))
            print(line.rstrip(), flush=True)
    for note in notes:
        print(f'  ({note})')
    for failure in failures:
        print(f'bench: {failure}', file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str], compiler: Path) -> int:
    cli = argparse.ArgumentParser(prog='python3 -m tools.core bench', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('-k', dest='words', help='kernels whose names contain any of these words')
    cli.add_argument('--runs', type=int, default=3, help='runs per binary (default 3)')
    cli.add_argument('--instructions', action='store_true', help='count user-space instructions instead of timing')
    cli.add_argument('--baseline', metavar='REV', help='compare instructions with REV\'s compiler (implies --instructions)')
    cli.add_argument('--limit', type=float, default=3.0, help='allowed increase in percent (default 3)')
    cli.add_argument('--counter', choices=('auto', 'perf', 'valgrind'), default='auto')
    args = cli.parse_args(argv)
    names = selected(args.words)
    if not names:
        cli.error(f'no kernel matches {args.words!r}; kernels: {" ".join(COUNTS)}')
    if args.instructions or args.baseline:
        return instructions(args, names, compiler)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    cc = os.environ.get('CC', 'cc')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    print(f'{"kernel":16} {"default":>9} {"release":>9} {"C -O2":>9} {"def/C":>6} {"rel/C":>6}  same output'
          f'   (median ms of {args.runs})', flush=True)
    mismatches = 0
    with tempfile.TemporaryDirectory(prefix='bench-', dir=SCRATCH) as temporary:
        work = Path(temporary)
        for name in names:
            source = prepare_source(name, work)
            binaries = {'default': work / f'{name}-default', 'release': work / f'{name}-release',
                        'c': work / f'{name}-c'}
            for mode in MODES:
                error = build(compiler, source, mode, binaries[mode], env)
                if error is not None:
                    raise RuntimeError(f'{name} ({mode}) failed to build:\n{error}')
            c_source = BENCH / f'{C_SOURCE.get(name, name)}.c'
            subprocess.run([cc, '-O2', f'-I{BENCH}', c_source, '-o', binaries['c']],
                           check=True, capture_output=True, text=True, timeout=120)
            times = {label: [] for label in binaries}
            checksums = set()
            for _ in range(args.runs):
                for label, binary in binaries.items():
                    checksum, nanoseconds = run([binary], COUNTS[name])
                    checksums.add(checksum)
                    times[label].append(nanoseconds / 1e6)
            ms = {label: statistics.median(values) for label, values in times.items()}
            same = len(checksums) == 1
            mismatches += not same
            ratio = lambda label: f'{ms[label] / ms["c"]:6.2f}' if ms['c'] > 0 else '     -'
            print(f'{name:16} {ms["default"]:9.2f} {ms["release"]:9.2f} {ms["c"]:9.2f} '
                  f'{ratio("default")} {ratio("release")}  {"yes" if same else "NO " + str(sorted(checksums))}',
                  flush=True)
    return 1 if mismatches else 0
