"""Compile-speed gate: user-space instructions to compile a fixed panel.

Compares this checkout's compiler (working tree) with a base commit's and fails
when any panel item needs more than --limit percent more instructions. Each
compiler is its commit's own fixed point (its sources built by a compiler with
the same sources) and uses its commit's library, so the counts cover compiler
and library changes alike. Inputs are this checkout's; a base that cannot
compile one falls back to its own copy and says so.

A line `speed: accept <reason>` in a commit message between the base and HEAD
waives the base comparison. A --checkpoint comparison is never waived: move the
checkpoint tag after reviewing accepted costs.

Counts come from perf_event_open (count_instructions.c), or from valgrind's
cachegrind where hardware counters are unavailable (CI's virtual machines).

--critical counts the critical path instead (the north-star gate): each
compiler builds the wall panel with --workers emission workers, and every
process is counted apart (count_critical.c); the compiler's own instructions
plus its largest worker's approximate wall time under ideal parallelism, and
unlike wall time do not depend on the machine's load. --wall also measures
wall-clock milliseconds, reported only: pinned to one logical CPU per physical
core where possible, runs interleaving base and candidate, median of --runs.
"""
from __future__ import annotations

import argparse
from tools.filelock import lock_exclusive
import hashlib
import json
import os
import random
import re
import resource
import shutil
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.compiler import speed_corpus

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '__dewycache__' / 'speed'
COUNTER_SOURCE = Path(__file__).with_name('count_instructions.c')
CRITICAL_SOURCE = Path(__file__).with_name('count_critical.c')
GAME = 'examples/dunes.dewy'
SYNTHETIC_FUNCTIONS = 1000
STABLE = 1e-4          # two runs of one item must agree within 0.01%
KEEP_BASES = 16        # cached base compilers kept (most recently used)
IPS = 6.3e9            # compiler instructions per second on the reference machine (compile_throughput.md)
CORPUS_WORKERS = (1, 4)
CORPUS_JOBS = 2        # programs compiled at once; critical-path counts do not depend on load
ACCEPT = re.compile(r'^speed: accept\s+(\S.*)$', re.MULTILINE)


def generate_dewy(count: int) -> str:
    """Synthetic program (same algorithm and constants as Sloppy's genbench.py)."""
    rng = random.Random(1)
    parts = ['Item:type=[x:float64 y:float64 id:int64]']
    for i in range(count):
        k = rng.randint(2, 9)
        parts.append(f'''work{i}=(a:int64 b:float64 items:array<Item>):>float64=>{{
    let total:float64=0.0
    let count=0
    loop j in [0..a) {{
        let v=float64(j*{k})+b
        if v >? {k*10}.0 {{total+=v*0.5}}
        else if j%{k}=?0 {{total-=v/{k}.0}}
        else {{count+=1}}
    }}
    loop it in items {{
        if it.id%{k}=?1 {{total+=it.x*it.y}}
        else {{total+=sqrt(abs(it.x-it.y))}}
    }}
    let s="item {i}"
    if s.length >? {k} {{total+=float64(s.length)}}
    loop count >? {k} {{
        count-={k+1}
        total*=1.0001
    }}
    return total+float64(count)
}}''')
    parts.append('let items:array<Item>=[]\nloop i in [0..100) {items.push(Item[x=float64(i) y=float64(i)*0.5 id=i])}\nlet acc:float64=0.0')
    parts.extend(f'acc+=work{i}({i%50} {i}.0 items)' for i in range(count))
    parts.append('printl"{acc}"')
    return '\n'.join(parts) + '\n'


def counter_result(stderr: str) -> int:
    """Instructions from count_instructions' final JSON line; reject multiplexed counts."""
    try:
        row = json.loads(stderr.splitlines()[-1])
    except (ValueError, IndexError) as error:
        raise ValueError('Missing hardware instruction count') from error
    keys = ('instructions', 'enabled_ns', 'running_ns')
    if not isinstance(row, dict) or any(type(row.get(k)) is not int or row[k] <= 0 for k in keys):
        raise ValueError('Invalid hardware instruction count')
    if row['enabled_ns'] != row['running_ns']:
        raise ValueError('Multiplexed hardware instruction count')
    return row['instructions']


def cachegrind_result(stderr: str) -> int:
    refs = re.findall(r'I\s+refs:\s+([\d,]+)', stderr)
    if not refs:
        raise ValueError('Missing cachegrind instruction count')
    return int(refs[-1].replace(',', ''))


def accepted(log: str) -> list[str]:
    """Reasons from `speed: accept <reason>` lines in commit messages."""
    return [reason.strip() for reason in ACCEPT.findall(log)]


def stable(first: int, second: int) -> bool:
    return abs(first - second) <= STABLE * max(first, second)


def delta(base: int, candidate: int) -> float:
    return (candidate - base) / base * 100


def clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update({'SLOPPY_EMIT_WORKERS': '1', **extra})
    return env


def git(*args, cwd: Path = ROOT) -> str:
    run = subprocess.run(['git', *map(str, args)], cwd=cwd, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(f'git {" ".join(map(str, args))}: {run.stderr.strip()}')
    return run.stdout.strip()


class Counter:
    def __init__(self, kind: str):
        self.kind = kind
        self.binary = None
        if kind in ('auto', 'perf'):
            source = COUNTER_SOURCE.read_bytes()
            self.binary = CACHE / f'count-instructions-{hashlib.sha256(source).hexdigest()[:12]}'
            if not self.binary.exists():
                temporary = self.binary.with_suffix('.tmp')
                subprocess.run([os.environ.get('CC', 'cc'), '-O2', '-Wall', '-Wextra', COUNTER_SOURCE,
                                '-o', temporary], check=True, capture_output=True, text=True)
                temporary.replace(self.binary)
            probe = subprocess.run([self.binary, '/bin/true'], capture_output=True, text=True)
            if probe.returncode == 0:
                self.kind = 'perf'
            elif kind == 'perf':
                raise RuntimeError(f'perf counters unavailable: {probe.stderr.strip()}')
            else:
                self.kind = 'valgrind'
        if self.kind == 'valgrind' and not shutil.which('valgrind'):
            raise RuntimeError('no instruction counters: perf_event_open failed and valgrind is not installed')

    @property
    def label(self) -> str:
        return 'perf counters' if self.kind == 'perf' else 'valgrind cachegrind'

    def count(self, command: list, env: dict) -> int:
        return self.run(command, env)[0]

    def run(self, command: list, env: dict) -> tuple[int, str]:
        """The command's user-space instructions and its stdout."""
        if self.kind == 'perf':
            run = subprocess.run([self.binary, *command], cwd=ROOT, env=env, capture_output=True, text=True)
            if run.returncode:
                raise CompileError(run.stdout + run.stderr)
            return counter_result(run.stderr), run.stdout
        run = subprocess.run(['valgrind', '--tool=cachegrind', '--cache-sim=no',
                              '--cachegrind-out-file=/dev/null', *command],
                             cwd=ROOT, env=env, capture_output=True, text=True)
        if run.returncode:
            raise CompileError(run.stdout + run.stderr)
        return cachegrind_result(run.stderr), run.stdout


class CompileError(RuntimeError):
    pass


def build_compiler(seed: Path, sources: Path, output: Path, log: Path) -> None:
    env = clean_env(DEWY_CORE_LIB=str(sources / 'lib'))
    run = subprocess.run([seed, 'build', sources / 'compiler/main.jo', '-o', output],
                         cwd=sources, env=env, capture_output=True, text=True, timeout=300)
    log.write_text(run.stdout + run.stderr)
    if run.returncode:
        raise CompileError(f'{seed} could not build {sources / "compiler/main.jo"}; see {log}')


def candidate_compiler(current: Path) -> Path:
    """This checkout's fixed point: its sources built by its own sources' logic."""
    from tools.core import source_identity

    identity = source_identity(ROOT)[:16]
    directory = CACHE / 'candidate'
    output = directory / identity / 'dewy-core'
    if output.exists():
        return output
    if directory.exists():
        shutil.rmtree(directory)
    output.parent.mkdir(parents=True)
    temporary = output.with_suffix('.tmp')
    build_compiler(current, ROOT, temporary, output.parent / 'build.log')
    temporary.replace(output)
    return output


def base_compiler(revision: str, current: Path) -> tuple[Path, bool]:
    """A commit's fixed-point compiler with its compiler/, lib/ and examples/, cached by hash."""
    bases = CACHE / 'base'
    output = bases / revision
    binary = output / 'bin/dewy-core'
    if binary.exists():
        os.utime(output)
        return output, False
    bases.mkdir(parents=True, exist_ok=True)
    work = CACHE / f'work-{revision[:12]}-{time.time_ns()}'
    tree = work / 'tree'
    work.mkdir()
    git('worktree', 'add', '--quiet', '--detach', tree, revision)
    try:
        (work / 'bin').mkdir()
        first = work / 'bin/dewy-core-first'
        try:
            build_compiler(current, tree, first, work / 'first.log')
        except CompileError:
            # Its sources need what this compiler no longer accepts: its own C bootstrap.
            print(f'(base {revision[:10]}: this compiler cannot build it; using its C bootstrap)',
                  file=sys.stderr, flush=True)
            boot = work / 'bootstrap'
            run = subprocess.run([sys.executable, '-m', 'tools.compiler.build', '--bootstrap', '--output', boot],
                                 cwd=tree, env=clean_env(), capture_output=True, text=True, timeout=900)
            if run.returncode:
                raise CompileError(f'base {revision[:10]} bootstrap failed:\n{run.stdout}{run.stderr}')
            shutil.copy2(boot / 'bin/dewy-core', first)
        build_compiler(first, tree, work / 'bin/dewy-core', work / 'self.log')
        first.unlink()
        for name in ('compiler', 'lib', 'examples'):
            shutil.copytree(tree / name, work / name)
    finally:
        subprocess.run(['git', 'worktree', 'remove', '--force', tree], cwd=ROOT, capture_output=True)
        shutil.rmtree(tree, ignore_errors=True)
    if output.exists():
        shutil.rmtree(work)
    else:
        work.replace(output)
    cached = sorted(bases.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in cached[KEEP_BASES:]:
        shutil.rmtree(stale, ignore_errors=True)
    return output, True


class Toolchain:
    def __init__(self, label: str, binary: Path, lib: Path, inputs: Path | None = None):
        self.label, self.binary, self.lib, self.inputs = label, binary, lib, inputs


def panel(release: bool) -> list[tuple[str, str, list[str]]]:
    synthetic = CACHE / 'panel' / f'synthetic-{SYNTHETIC_FUNCTIONS}.dewy'
    generated = generate_dewy(SYNTHETIC_FUNCTIONS)
    if not synthetic.exists() or synthetic.read_text() != generated:
        synthetic.parent.mkdir(parents=True, exist_ok=True)
        synthetic.write_text(generated)
    items = [('self-build', 'compiler/main.jo', []),
             ('synthetic-22k', str(synthetic), []),
             ('game', GAME, [])]
    if release:
        # (compiler/main.jo's build block already selects release mode: no second self-build)
        items.append(('synthetic-22k --release', str(synthetic), ['--release']))
    return items


def stage(toolchain: Toolchain) -> Path:
    """Copy a toolchain to one fixed path: path strings (and their hashes) then
    match between compilers, which otherwise moves counts by ~0.1%."""
    active = CACHE / 'panel' / 'active'
    marker = active / 'from'
    if marker.exists() and marker.read_text() == str(toolchain.binary):
        return active
    shutil.rmtree(active, ignore_errors=True)
    (active / 'bin').mkdir(parents=True)
    shutil.copy2(toolchain.binary, active / 'bin/dewy-core')
    shutil.copytree(toolchain.lib, active / 'lib')
    marker.write_text(str(toolchain.binary))
    return active


def measure(counter: Counter, toolchain: Toolchain, source: str, flags: list[str], notes: list[str]) -> int:
    output = CACHE / 'panel' / 'program'
    active = stage(toolchain)
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'))

    def twice(path: Path) -> int:
        command = [active / 'bin/dewy-core', 'build', path, *flags, '-o', output]
        first, second = counter.count(command, env), counter.count(command, env)
        if not stable(first, second):
            raise RuntimeError(f'unstable counts for {toolchain.label} {source}: {first} vs {second}')
        return min(first, second)

    path = ROOT / source
    try:
        return twice(path)
    except CompileError as error:
        if toolchain.inputs is None or Path(source).is_absolute():
            raise RuntimeError(f'{toolchain.label} cannot build {source}:\n{str(error)[-2000:]}')
        notes.append(f'{toolchain.label} cannot build this checkout\'s {source}; measured its own copy')
        return twice(toolchain.inputs / source)


HELLO = 'printl"hello"\n'


def wall_panel() -> list[tuple[str, str]]:
    synthetic = panel(False)[1][1]
    hello = CACHE / 'panel' / 'hello.dewy'
    if not hello.exists() or hello.read_text() != HELLO:
        hello.write_text(HELLO)
    return [('synthetic-22k', synthetic), ('game', GAME), ('hello', str(hello))]


def physical_cpus() -> list[int]:
    """One allowed logical CPU per physical core (the first sibling), in order."""
    allowed = sorted(os.sched_getaffinity(0))
    chosen, seen = [], set()
    for cpu in allowed:
        siblings = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list')
        try:
            core = siblings.read_text().strip()
        except OSError:
            core = str(cpu)
        if core not in seen:
            seen.add(core)
            chosen.append(cpu)
    return chosen


def stage_wall(toolchain: Toolchain, role: str) -> Path:
    """A toolchain copied to a directory of its own, so runs can interleave."""
    active = CACHE / 'panel' / f'wall-{role}'
    marker = active / 'from'
    if marker.exists() and marker.read_text() == str(toolchain.binary):
        return active
    shutil.rmtree(active, ignore_errors=True)
    (active / 'bin').mkdir(parents=True)
    shutil.copy2(toolchain.binary, active / 'bin/dewy-core')
    shutil.copytree(toolchain.lib, active / 'lib')
    marker.write_text(str(toolchain.binary))
    return active


def wall_once(active: Path, source: Path, workers: int, cpus: list[int]) -> tuple[float, float]:
    """Wall and CPU milliseconds of one build."""
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'), SLOPPY_EMIT_WORKERS=str(workers))
    command = [str(active / 'bin/dewy-core'), 'build', str(source), '-o', str(active / 'program')]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                         preexec_fn=(lambda: os.sched_setaffinity(0, cpus)) if cpus else None)
    wall = (time.perf_counter() - started) * 1000
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if run.returncode:
        raise CompileError(run.stdout + run.stderr)
    cpu = (after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime) * 1000
    return wall, cpu


def critical_counter() -> Path:
    source = CRITICAL_SOURCE.read_bytes()
    binary = CACHE / f'count-critical-{hashlib.sha256(source).hexdigest()[:12]}'
    if not binary.exists():
        temporary = binary.with_suffix('.tmp')
        subprocess.run([os.environ.get('CC', 'cc'), '-O2', '-Wall', '-Wextra', CRITICAL_SOURCE, '-o', temporary],
                       check=True, capture_output=True, text=True)
        temporary.replace(binary)
    return binary


def critical_result(stderr: str) -> tuple[int, int]:
    """(critical path, total) instructions from count_critical's final JSON line."""
    try:
        row = json.loads(stderr.splitlines()[-1])
        return int(row['critical']), int(row['total'])
    except (ValueError, IndexError, KeyError, TypeError) as error:
        raise ValueError('Missing critical-path instruction count') from error


def critical_once(counter: Path, active: Path, source: Path, workers: int,
                  output: Path | None = None) -> tuple[int, int]:
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'), SLOPPY_EMIT_WORKERS=str(workers))
    run = subprocess.run([counter, active / 'bin/dewy-core', 'build', source, '-o', output or active / 'program'],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    if run.returncode:
        raise CompileError(run.stdout + run.stderr)
    return critical_result(run.stderr)


def critical_main(args, staged: dict[str, Path], labels: str, workers: list[int], limit: float) -> list:
    """Critical-path instructions of the wall panel; returns failures."""
    counter = critical_counter()
    order = list(staged)
    print('compile critical path, G instructions (own + largest worker; total in parentheses): ' + labels)
    failures = []
    for name, source in wall_panel():
        path = Path(source) if Path(source).is_absolute() else ROOT / source
        for n in workers:
            # (the least of two: the compiler's own count varies a little with how its pipes are read)
            got = {role: min(critical_once(counter, staged[role], path, n) for _ in range(2)) for role in order}
            line = f'  {name:15} {n} worker{"s" if n != 1 else " "}'
            if 'base' in got:
                (old, old_total), (new, new_total) = got['base'], got['candidate']
                change = round(delta(old, new), 2) + 0.0
                over = change > limit
                if over:
                    failures.append((name, n, change))
                line += (f'  {old / 1e9:7.4f} -> {new / 1e9:7.4f}  {change:+6.2f}%'
                         f'   ({old_total / 1e9:.4f} -> {new_total / 1e9:.4f})' + ('  <-' if over else ''))
            else:
                line += f'  {got["candidate"][0] / 1e9:7.4f}   ({got["candidate"][1] / 1e9:.4f})'
            print(line, flush=True)
    return failures


def corpus_critical(counter: Path, staged: dict[str, Path], programs: list[Path]) -> dict:
    """{program: {role: {workers: critical-path instructions}}}, or None for a program some compiler cannot build."""
    out = CACHE / 'panel' / 'corpus'
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    tasks = [(program, role, n) for program in programs for role in staged for n in CORPUS_WORKERS]

    def run(numbered):
        number, (program, role, n) = numbered
        try:
            return critical_once(counter, staged[role], program, n, out / str(number))[0]
        except CompileError as error:
            return error
    with ThreadPoolExecutor(CORPUS_JOBS) as pool:
        results = list(pool.map(run, enumerate(tasks)))
    shutil.rmtree(out, ignore_errors=True)
    table: dict = {program: {role: {} for role in staged} for program in programs}
    for (program, role, n), result in zip(tasks, results):
        if isinstance(result, CompileError):
            if table[program] is not None:
                reason = [line for line in str(result).splitlines() if line.strip() and not line.startswith('{')]
                print(f'  (left out {program.relative_to(ROOT)}: {role} cannot build it: '
                      f'{(reason or ["?"])[0][:150]})', file=sys.stderr)
            table[program] = None
        elif table[program] is not None:
            table[program][role][n] = result
    return table


def corpus_library_lines(active: Path, program: Path, physical: int) -> int:
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'))
    run = subprocess.run([active / 'bin/dewy-core', 'build', program, '--time', '-o', active / 'program'],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    if run.returncode:
        raise CompileError(run.stdout + run.stderr)
    return speed_corpus.library_lines(run.stderr, physical)


def corpus_wall(staged: dict[str, Path], programs: list[Path], n: int, runs: int, cpus: list[int]) -> dict:
    """Median milliseconds to compile every program once, per role (runs interleaved)."""
    order = list(staged)
    for role in order:
        for program in programs:
            wall_once(staged[role], program, n, cpus)
    totals = {role: [] for role in order}
    for k in range(runs):
        for role in (order if k % 2 == 0 else order[::-1]):
            totals[role].append(sum(wall_once(staged[role], program, n, cpus)[0] for program in programs))
    return {role: statistics.median(times) for role, times in totals.items()}


def corpus_main(args, staged: dict[str, Path], labels: str, limit: float) -> list:
    """Per-corpus line counts and critical-path instructions (lines/s with --wall); returns failures."""
    counter = critical_counter()
    order = list(staged)
    hello = Path(wall_panel()[2][1])
    floor = {role: {n: critical_once(counter, staged[role], hello, n)[0] for n in CORPUS_WORKERS} for role in order}
    cpus = physical_cpus() if args.wall and not args.no_pin else []
    print('compile corpora, critical-path instructions, G (own + largest worker; per program, then summed): ' + labels)
    failures = []
    for name, programs in speed_corpus.corpora(CACHE / 'panel' / 'bench-game').items():
        if not programs:
            print(f'  {name}: no programs yet')
            continue
        table = corpus_critical(counter, staged, programs)
        kept = [program for program in programs if table[program] is not None]
        if not kept:
            print(f'  {name}: no program every compiler can build')
            continue
        counts = [speed_corpus.root_counts(program) for program in programs if program in kept]
        lines = sum(source for source, _ in counts)
        library = sum(corpus_library_lines(staged['candidate'], program, physical)
                      for program, (_, physical) in zip(kept, counts))
        print(f'  {name}: {len(kept)} programs, {lines} root lines, {library} library lines loaded (summed over compiles)')
        total = {role: {n: sum(table[program][role][n] for program in kept) for n in CORPUS_WORKERS} for role in order}
        walls = {n: corpus_wall(staged, kept, n, args.runs, cpus) for n in CORPUS_WORKERS} if args.wall else {}
        for n in CORPUS_WORKERS:
            new = total['candidate'][n]
            line = f'    {n} worker{"s" if n != 1 else " "}  '
            if 'base' in total:
                old = total['base'][n]
                change = round(delta(old, new), 2) + 0.0
                over = change > limit
                if over:
                    failures.append((name, n, change))
                line += f'{old / 1e9:8.4f} -> {new / 1e9:8.4f}  {change:+6.2f}%' + (' <-' if over else '   ')
            else:
                line += f'{new / 1e9:8.4f}'
            net = new - len(kept) * floor['candidate'][n]
            line += f'   {new / lines / 1e3:7.1f} k inst/line ({net / lines / 1e3:.1f} net of hello)'
            if args.wall:
                ms = walls[n]
                line += f'   {lines / ms["candidate"] * 1e3:9.0f} lines/s'
                if 'base' in ms:
                    line += f' (base {lines / ms["base"] * 1e3:.0f})'
            else:
                line += f'   est. {lines / (new / IPS):9.0f} lines/s' if n == max(CORPUS_WORKERS) else ''
            print(line.rstrip(), flush=True)
    return failures


def wall_main(args, toolchains: dict[str, Toolchain]) -> int:
    cpus = physical_cpus() if not args.no_pin else []
    workers = [int(w) for w in args.workers.split(',')]
    limit = 1.0 if args.limit is None else args.limit
    staged = {role: stage_wall(toolchain, role) for role, toolchain in toolchains.items()}
    order = list(staged)
    labels = ' -> '.join(f'{role} {toolchains[role].label}' for role in order)
    if args.corpus:
        failures = corpus_main(args, staged, labels, limit)
        for name, n, change in failures:
            print(f'speed: corpus {name} with {n} workers needs {change:+.2f}% critical-path instructions vs base '
                  f'(limit {limit}%)', file=sys.stderr)
        return 1 if failures else 0
    failures = critical_main(args, staged, labels, workers, limit)
    for name, n, change in failures:
        print(f'speed: {name} with {n} workers needs {change:+.2f}% critical-path instructions vs base '
              f'(limit {limit}%)', file=sys.stderr)
    if not args.wall:
        return 1 if failures else 0
    load = os.getloadavg()[0]
    print(f'compile wall time, ms (median of {args.runs}, interleaved; '
          + (f'pinned to CPUs {",".join(map(str, cpus))}' if cpus else 'unpinned')
          + f'; load {load:.1f}; reported, not gated): ' + labels)
    for name, source in wall_panel():
        path = Path(source) if Path(source).is_absolute() else ROOT / source
        for n in workers:
            walls = {role: [] for role in order}
            cpu = {role: [] for role in order}
            for role in order:          # (warm the page cache)
                wall_once(staged[role], path, n, cpus)
            for k in range(args.runs):
                for role in (order if k % 2 == 0 else order[::-1]):
                    w, c = wall_once(staged[role], path, n, cpus)
                    walls[role].append(w)
                    cpu[role].append(c)
            med = {role: statistics.median(walls[role]) for role in order}
            line = f'  {name:15} {n} worker{"s" if n != 1 else " "}'
            if 'base' in med:
                change = round(delta(med['base'], med['candidate']), 1) + 0.0
                line += (f'  {med["base"]:7.1f} -> {med["candidate"]:7.1f}  {change:+5.1f}%'
                         f'   (cpu {statistics.median(cpu["base"]):6.1f} -> {statistics.median(cpu["candidate"]):6.1f})')
            else:
                line += f'  {med["candidate"]:7.1f}   (cpu {statistics.median(cpu["candidate"]):6.1f})'
            print(line, flush=True)
    return 1 if failures else 0


def resolve(revision: str) -> str:
    return git('rev-parse', '--verify', f'{revision}^{{commit}}')


def main(argv: list[str], current: Path) -> int:
    cli = argparse.ArgumentParser(prog='python3 -m tools.core speed', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--base', default='HEAD~1', help='commit to compare with (default HEAD~1)')
    cli.add_argument('--checkpoint', metavar='TAG', help='also compare with this fixed revision, e.g. speed-checkpoint')
    cli.add_argument('--limit', type=float, default=None, help='allowed increase in percent (default 1.0)')
    cli.add_argument('--release', action='store_true', help='also measure release builds')
    cli.add_argument('--counter', choices=('auto', 'perf', 'valgrind'), default='auto')
    cli.add_argument('--critical', action='store_true',
                     help='count critical-path instructions (own + largest worker) at --workers')
    cli.add_argument('--corpus', action='store_true',
                     help='critical-path instructions, lines and lines/s of representative program corpora')
    cli.add_argument('--wall', action='store_true',
                     help='--critical, and also report wall-clock time (with --corpus: measured lines/s)')
    cli.add_argument('--workers', default='1,2,4', help='--critical/--wall: emission worker counts (default 1,2,4)')
    cli.add_argument('--runs', type=int, default=7, help='--wall: runs per compiler (default 7)')
    cli.add_argument('--no-pin', action='store_true', help='--wall: do not pin to one CPU per core')
    args = cli.parse_args(argv)
    if args.wall or args.critical or args.corpus:
        CACHE.mkdir(parents=True, exist_ok=True)
        with (CACHE / 'speed.lock').open('w') as lock:
            lock_exclusive(lock)
            toolchains = {}
            if args.base is not None:
                commit = resolve(args.base)
                directory, built = base_compiler(commit, current)
                if built:
                    print(f'(built base compiler {commit[:10]})', file=sys.stderr, flush=True)
                toolchains['base'] = Toolchain(commit[:10], directory / 'bin/dewy-core', directory / 'lib')
            dirty = bool(git('status', '--porcelain', '--untracked-files=no'))
            label = 'working tree' if dirty else git('rev-parse', '--short=10', 'HEAD')
            toolchains['candidate'] = Toolchain(label, candidate_compiler(current), ROOT / 'lib')
            return wall_main(args, toolchains)
    if args.limit is None:
        args.limit = 1.0
    started = time.perf_counter()
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / 'speed.lock').open('w') as lock:
        lock_exclusive(lock)
        counter = Counter(args.counter)
        candidate = Toolchain('candidate', candidate_compiler(current), ROOT / 'lib')
        references = {}
        for role, revision in (('base', args.base), ('checkpoint', args.checkpoint)):
            if revision is None:
                continue
            commit = resolve(revision)
            directory, built = base_compiler(commit, current)
            if built:
                print(f'(built {role} compiler {commit[:10]})', file=sys.stderr, flush=True)
            references[role] = (revision, commit, Toolchain(f'{role} {commit[:10]}', directory / 'bin/dewy-core',
                                                            directory / 'lib', directory))
        base_commit = references['base'][1]
        reasons = accepted(git('log', '--format=%B', f'{base_commit}..HEAD'))
        dirty = bool(git('status', '--porcelain', '--untracked-files=no'))
        target = 'working tree' if dirty else git('rev-parse', '--short=10', 'HEAD')
        print(f'compile speed, G instructions ({counter.label}, 1 emission worker): '
              + ', '.join(f'{role} {revision} ({commit[:10]})' for role, (revision, commit, _) in references.items())
              + f' -> {target}')
        notes: list[str] = []
        failures = []
        for name, source, flags in panel(args.release):
            new = measure(counter, candidate, source, flags, notes)
            line = f'  {name:26}'
            for role, (revision, _, toolchain) in references.items():
                old = measure(counter, toolchain, source, flags, notes)
                change = round(delta(old, new), 2) + 0.0
                over = change > args.limit
                if over:
                    failures.append((role, name, change))
                prefix = '' if role == 'base' else f'   {revision}'
                line += f'{prefix} {old / 1e9:8.4f} -> {new / 1e9:8.4f}  {change:+6.2f}%' + (' <-' if over else '   ')
            print(line.rstrip(), flush=True)
        for note in dict.fromkeys(notes):
            print(f'  ({note})')
        print(f'  ({time.perf_counter() - started:.0f} s)')
    base_failures = [f for f in failures if f[0] == 'base']
    other_failures = [f for f in failures if f[0] != 'base']
    if base_failures and reasons:
        print('speed: base regression accepted: ' + '; '.join(reasons))
        base_failures = []
    remaining = base_failures + other_failures
    for role, name, change in remaining:
        print(f'speed: {name} needs {change:+.2f}% instructions vs {role} (limit {args.limit}%)', file=sys.stderr)
    if remaining:
        print('speed: add a line `speed: accept <reason>` to the commit message when the cost is intended',
              file=sys.stderr)
    return 1 if remaining else 0
