"""Compile-speed gate: user-space instructions to compile a fixed panel.

Compares this checkout's compiler (working tree) with a base commit's and fails
when any panel item needs more than --limit percent more instructions. The
panel: the self-build, synthetic-22k and the game; small-program latency (hello
and the median tier 1-3 ladder program); large-program throughput (each tier-4
flagship). Compile throughput counts every source line the compiler processes:
the program's, the library lines it reached (lazy bodies nobody asked for left
out) and each generic instance's declaration once per instance. A yardstick
table reports the candidate's lines (all, user-only, fan-out), estimated
milliseconds and lines/s (instructions at the reference rate IPS), and its
instructions split into root, library and shared work (`build --time`); a cost
model gives instructions per processed node by phase. The gates: the per-item
instruction comparison with the base, the flagship panel's all-lines
throughput (it may not drop more than --limit percent unless the panel got
cheaper) and hello-world latency (<= 20 ms; reported until it is under). Each
compiler is its commit's own fixed point (its sources built by a compiler with
the same sources) and uses its commit's library, so the counts cover compiler
and library changes alike. Inputs are this checkout's. A base that cannot
compile one of them (it predates a rule the program now relies on) is measured
on its own, older copy of the program, so that row compares two different
programs. The gate says so loudly and splits the row: the candidate also
builds the base's copy (compiler alone), and its two costs, on the old and the
new source, give the source's own growth. The compiler's share is gated as
usual; a source that grew more than the limit (or cannot be split) fails unless
a `speed: accept` line names the program (its directory name, or its number).
Such rows are left out of the throughput and phase comparisons.

A program whose own files changed since the base is measured one more time:
both compilers run on this source, so the row's change is the compiler alone
and hides the program's own growth. The candidate also builds the base's copy
(only for programs that changed), and the two give the source alone. Growth
over the limit fails unless a `speed: accept` line names the program.

Both compilers build the same compiler source in the self-build row, so a cost
that the new source adds to its own compile (such as an import cycle that sends
the compiler down a slow path) is paid on both sides and never shows. The
"self-build source cost" row holds the candidate compiler fixed and builds the
base's compiler source, then this checkout's. The compiler grows a little with
most changes, so it fails only above SOURCE_LIMIT percent (or --limit if larger).

A line `speed: accept <reason>` in a commit message between the base and HEAD
waives the base comparison. A --checkpoint comparison is never waived: move the
checkpoint tag after reviewing accepted costs (a program's own growth against
the checkpoint is the one exception: an accept line that names it, between the
checkpoint and HEAD, acknowledges it).

Counts come from perf_event_open (count_instructions.c), or from valgrind's
cachegrind where hardware counters are unavailable (CI's virtual machines).

--critical counts the critical path instead (the north-star gate): each
compiler builds the wall panel with --workers emission workers, and every
process is counted apart (count_critical.c); the compiler's own instructions
plus its largest worker's approximate wall time under ideal parallelism, and
unlike wall time do not depend on the machine's load. --wall also measures
wall-clock milliseconds, reported only: pinned to one logical CPU per physical
core where possible, runs interleaving base and candidate, median of --runs.

For layout/padding changes, also run --cycles --cpu N --runs 15. Retired
instructions count NOPs as work; cycles expose their different execution cost.
This hardware-only report pins each compile to the selected allowed CPU, warms
both hosts, alternates their order, and reports medians and min/max plus load
before/after. Use an idle physical core (including its SMT sibling), fixed CPU
frequency policy and identical inputs; load, interrupts and frequency changes
still affect cycles. It reports every normal panel item alongside instructions;
cycles are not converted to reference lines/s. --limit explicitly gates cycles;
without it the cycle report is diagnostic. It never waives a cycle regression
via commit messages. The normal instruction gate remains a separate run.
"""
from __future__ import annotations

import argparse
from tools.filelock import lock_exclusive
from tools import headless
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
from dataclasses import dataclass
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
SOURCE_LIMIT = 5.0     # percent: the candidate compiling the base's compiler source, then this checkout's
ACCEPT = re.compile(r'^speed: accept\s+(\S.*)$', re.MULTILINE)


def generate_dewy(count: int) -> str:
    """Synthetic program (same algorithm and constants as the original generator)."""
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


def counter_result(stderr: str, metric: str = 'instructions') -> int:
    """Selected hardware event from the final JSON line; reject multiplexed counts."""
    try:
        row = json.loads(stderr.splitlines()[-1])
    except (ValueError, IndexError) as error:
        raise ValueError(f'Missing hardware {metric} count') from error
    keys = (metric, 'enabled_ns', 'running_ns')
    if not isinstance(row, dict) or any(type(row.get(k)) is not int or row[k] <= 0 for k in keys):
        raise ValueError(f'Invalid hardware {metric} count')
    if row['enabled_ns'] != row['running_ns']:
        raise ValueError(f'Multiplexed hardware {metric} count')
    return row[metric]


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
    env = {k: v for k, v in os.environ.items() if not k.startswith('DEWY_')}
    env.update({'DEWY_EMIT_WORKERS': '1', **extra})
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


def base_tests(revision: str, output: Path) -> None:
    """The base commit's own panel sources (tests/ladder), so flagship rows compare like for like."""
    if (output / 'tests/ladder').exists():
        return
    (output / 'tests').mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(['git', 'archive', revision, 'tests/ladder'], cwd=ROOT, capture_output=True, check=True)
    subprocess.run(['tar', '-x', '-C', str(output)], input=archive.stdout, check=True)


def base_compiler(revision: str, current: Path) -> tuple[Path, bool]:
    """A commit's fixed-point compiler with its compiler/, lib/ and examples/, cached by hash."""
    bases = CACHE / 'base'
    output = bases / revision
    binary = output / 'bin/dewy-core'
    if binary.exists():
        os.utime(output)
        base_tests(revision, output)
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
        base_tests(revision, work)
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
    """(name, source, flags): the compiler itself, synthetic and the game, then the latency probes (hello, the
    median ladder program) and the throughput panel (each tier-4 flagship)."""
    synthetic = CACHE / 'panel' / f'synthetic-{SYNTHETIC_FUNCTIONS}.dewy'
    generated = generate_dewy(SYNTHETIC_FUNCTIONS)
    if not synthetic.exists() or synthetic.read_text() != generated:
        synthetic.parent.mkdir(parents=True, exist_ok=True)
        synthetic.write_text(generated)
    median = speed_corpus.median_ladder_program()
    items = [('self-build', 'compiler/main.jo', []),
             ('synthetic-22k', str(synthetic), []),
             ('game', GAME, []),
             ('hello', hello_source(), []),
             (f'ladder {median.parent.name}', str(median.relative_to(ROOT)), [])]
    items += [(f'flagship {path.parent.name}', str(path.relative_to(ROOT)), []) for path in speed_corpus.flagships()]
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


def measure_item(counter: Counter, toolchain: Toolchain, source: str, flags: list[str]) -> tuple[int, Path | None]:
    """The compiler's instructions for one source, and None; or, when a base cannot build this checkout's source,
    its instructions on its own copy and that copy's path (the count is then of a different program)."""
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
        return twice(path), None
    except CompileError as error:
        if toolchain.inputs is None or Path(source).is_absolute():
            raise RuntimeError(f'{toolchain.label} cannot build {source}:\n{str(error)[-2000:]}')
        own = toolchain.inputs / source
        return twice(own), own


def measure(counter: Counter, toolchain: Toolchain, source: str, flags: list[str], notes: list[str]) -> int:
    count, own = measure_item(counter, toolchain, source, flags)
    if own is not None:
        notes.append(f'FALLBACK: {toolchain.label} cannot build this checkout\'s {source}; measured its own copy')
    return count


@dataclass
class Fallback:
    """A panel row whose reference compiler could not build this checkout's source: `old` is the reference on
    its own copy, `new` the candidate on this source, `same` the candidate on the reference's copy (the compiler
    alone; None when it cannot build that either)."""
    role: str
    name: str
    revision: str
    old: int
    new: int
    same: int | None

    @property
    def compiler(self) -> float | None:
        """Percent the candidate compiler costs over the reference, on the reference's source."""
        return None if self.same is None else round(delta(self.old, self.same), 2) + 0.0

    @property
    def growth(self) -> float | None:
        """Percent the source itself grew, for the candidate compiler."""
        return None if self.same is None else round(delta(self.same, self.new), 2) + 0.0

    def lines(self) -> list[str]:
        out = [f'    !! FALLBACK {self.name}: {self.role} {self.revision} cannot build this checkout\'s source, so the row '
               'above compares two different programs; its cost is not a compiler cost',
               f'       {self.role} on its old source       {self.old / 1e9:8.4f} G']
        if self.same is None:
            out.append('       candidate on the old source: it cannot build that either; no split')
        else:
            out.append(f'       candidate on the old source  {self.same / 1e9:8.4f} G  {self.compiler:+6.2f}%  (compiler alone)')
        out.append(f'       candidate on this source     {self.new / 1e9:8.4f} G  '
                   + (f'{self.growth:+6.2f}%  (this source\'s own growth)' if self.growth is not None else
                      f'{round(delta(self.old, self.new), 2):+6.2f}%  (against the old source: not split)'))
        return out


def names_item(reason: str, name: str) -> bool:
    """Does an accept reason name this panel row? Rows are named by their program (`ladder 84_tensor_broadcast`,
    `flagship 97_notes_service`: the directory name, or its number as a word) or by a word (`game`, `hello`)."""
    program = name.split(' ', 1)[1] if name.startswith(('ladder ', 'flagship ')) else name
    if program in reason:
        return True
    number = re.match(r'\d+(?=_)', program)
    word = number.group() if number else program.split()[0]
    return re.search(rf'(?<![\w.]){re.escape(word)}(?![\w]|\.\d)', reason, re.IGNORECASE) is not None


def growth_verdict(rows: list, limit: float, reasons: dict[str, list[str]], describe) -> tuple[list[str], list[str]]:
    """(failures, accepted) for source growth: a source that grew more than `limit` (or cannot be split) fails
    unless an accept line of its role's commit range names the program."""
    failures, waived = [], []
    for row in rows:
        if row.growth is not None and row.growth <= limit:
            continue
        named = [r for r in reasons.get(row.role, []) if names_item(r, row.name)]
        what = describe(row, limit)
        (waived if named else failures).append(f'{what}: accepted: {named[0]}' if named else what)
    return failures, waived


def fallback_verdict(fallbacks: list[Fallback], limit: float,
                     reasons: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """The growth verdict of the fallback rows (the reference measured an older copy of the source)."""
    return growth_verdict(fallbacks, limit, reasons, lambda fb, limit: (
        f'{fb.name}: {fb.role} {fb.revision} measured an older copy of the source'
        + (f'; this source grew {fb.growth:+.2f}% (limit {limit:g}%)' if fb.growth is not None
           else '; the candidate cannot build that copy, so the growth is unknown')
        + f' ({fb.old / 1e9:.4f} G old source -> {fb.new / 1e9:.4f} G this source)'))


def program_text(root: Path, source: str) -> dict[str, bytes]:
    """A program's own files under `root`: its entry and every file it imports by relative path."""
    top = root.resolve()
    files = {}
    for path in speed_corpus.root_files(top / source):
        try:
            name = str(path.relative_to(top))
        except ValueError:
            name = str(path)
        files[name] = path.read_bytes()
    return files


def source_drifted(inputs: Path | None, source: str) -> bool:
    """Does the program's source differ between a reference's checkout and this one? Only programs the
    reference holds (the ladder and the examples) can; the compiler itself has its own self-build row."""
    if inputs is None or Path(source).is_absolute() or source == 'compiler/main.jo' or not (inputs / source).is_file():
        return False
    return program_text(inputs, source) != program_text(ROOT, source)


@dataclass
class Drift:
    """A panel row whose reference compiler built this checkout's source, but whose source differs from the
    reference's own copy: `old` is the reference on this source, `new` the candidate on it, `same` the candidate on
    the reference's copy (None when it cannot build that). Both compilers run on one source in the row, so only
    this split shows the source's own growth."""
    role: str
    name: str
    revision: str
    old: int
    new: int
    same: int | None

    @property
    def compiler(self) -> float:
        """Percent the candidate compiler costs over the reference, on this source (the row's own change)."""
        return round(delta(self.old, self.new), 2) + 0.0

    @property
    def growth(self) -> float | None:
        """Percent the source itself grew, for the candidate compiler."""
        return None if self.same is None else round(delta(self.same, self.new), 2) + 0.0

    def lines(self) -> list[str]:
        out = [f'    ~~ SOURCE DRIFT {self.name}: this source differs from {self.role} {self.revision}\'s copy; the row '
               'above runs both compilers on this source, so it shows the compiler alone']
        if self.same is None:
            out.append('       candidate on the old source: it cannot build that; no split')
        else:
            out.append(f'       candidate on the old source  {self.same / 1e9:8.4f} G')
        out.append(f'       candidate on this source     {self.new / 1e9:8.4f} G  '
                   + (f'{self.growth:+6.2f}%  (source alone)' if self.growth is not None else '(growth unknown)'))
        out.append(f'       {self.role} on this source          {self.old / 1e9:8.4f} G  {self.compiler:+6.2f}%  '
                   '(compiler alone, the row above)')
        return out


def drift_verdict(drifts: list[Drift], limit: float, reasons: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """The growth verdict of the drifted rows: a program's own source growth over `limit` fails unless an accept
    line of its role's commit range names the program."""
    def describe(d: Drift, limit: float) -> str:
        if d.growth is None:
            return (f'{d.name}: its source differs from {d.role} {d.revision}\'s copy and the candidate cannot build '
                    f'that copy, so the growth is unknown ({d.new / 1e9:.4f} G this source)')
        return (f'{d.name}: its source differs from {d.role} {d.revision}\'s copy and grew {d.growth:+.2f}% '
                f'(limit {limit:g}%; {d.same / 1e9:.4f} G old source -> {d.new / 1e9:.4f} G this source)')

    return growth_verdict(drifts, limit, reasons, describe)


def source_row(counter: Counter, candidate: Toolchain, base: Toolchain, counts: dict[str, int], notes: list[str],
               limit: float, failures: list) -> None:
    """The candidate compiler builds the base's compiler source, then this checkout's (the self-build row's
    count): what the source change alone costs to compile."""
    name = 'self-build source cost'
    # Source paths are hashed by the compiler. Build each tree from the same
    # staging path so directory depth cannot masquerade as source growth.
    source = CACHE / 'panel' / 'source-cost' / 'compiler'
    def staged_count(tree: Path) -> int:
        shutil.rmtree(source, ignore_errors=True)
        shutil.copytree(tree / 'compiler', source)
        return measure(counter, candidate, str(source / 'main.jo'), [], notes)

    try:
        old = staged_count(base.inputs)
    except RuntimeError:
        notes.append('the candidate cannot build the base\'s compiler source; no source cost row')
        return
    new = staged_count(ROOT)
    change = round(delta(old, new), 2) + 0.0
    over = change > limit
    if over:
        failures.append(('base', f'{name} (candidate compiler, base -> this source)', change))
    print(f'  {name:26} {old / 1e9:8.4f} -> {new / 1e9:8.4f}  {change:+6.2f}%' + (' <-' if over else '')
          + f'  (candidate compiler: base -> this source; limit {limit:g}%)', flush=True)


HELLO = 'printl"hello"\n'


def hello_source() -> str:
    hello = CACHE / 'panel' / 'hello.dewy'
    if not hello.exists() or hello.read_text() != HELLO:
        hello.parent.mkdir(parents=True, exist_ok=True)
        hello.write_text(HELLO)
    return str(hello)


def wall_panel() -> list[tuple[str, str]]:
    synthetic = panel(False)[1][1]
    return [('synthetic-22k', synthetic), ('game', GAME), ('hello', hello_source())]


_reports: dict[tuple[str, str], str] = {}


def time_run(toolchain: Toolchain, source: str) -> str:
    """`build --time`'s report for one source: phases, source counts and the instruction split (kept: the
    yardstick, the cost model and the throughput gate read the same runs)."""
    key = (str(toolchain.binary), source)
    if key not in _reports:
        _reports[key] = time_report(toolchain, source)
    return _reports[key]


def time_report(toolchain: Toolchain, source: str) -> str:
    active = stage(toolchain)
    path = Path(source) if Path(source).is_absolute() else ROOT / source
    run = subprocess.run([active / 'bin/dewy-core', 'build', path, '--time', '-o', CACHE / 'panel' / 'program'],
                         cwd=ROOT, env=clean_env(DEWY_CORE_LIB=str(active / 'lib')), capture_output=True, text=True)
    if run.returncode and toolchain.inputs is not None and not Path(source).is_absolute():
        # (a base that cannot build this checkout's source reports on its own copy, as the panel measures it)
        run = subprocess.run([active / 'bin/dewy-core', 'build', toolchain.inputs / source, '--time', '-o',
                              CACHE / 'panel' / 'program'],
                             cwd=ROOT, env=clean_env(DEWY_CORE_LIB=str(active / 'lib')), capture_output=True, text=True)
    if run.returncode:
        raise CompileError(run.stdout + run.stderr)
    return run.stderr


# Track B0's cost model: each phase's instructions per processed syntax node (every node the compile made:
# the program's, the reached library's and the instances') on the flagship panel, against budgets. The goal is
# 250k processed lines/s at IPS, 25.2k instructions a line; the flagships make ~8 nodes a processed line
# (NODES_PER_LINE, measured when the metric changed), so ~3.15k instructions a node. A phase's budget per
# line splits that by phase. (row, build --time phases, budget per processed line)
GOAL_LINES_PER_SECOND = 250_000
NODES_PER_LINE = 8
PHASE_BUDGETS = [('lex+parse', ('load',), 3000), ('resolve+check', ('check',), 7000),
                 ('facts', ('facts',), None), ('effects', ('effects',), None),
                 ('facts+effects', ('facts', 'effects'), 4000), ('ownership', ('ownership',), None),
                 ('lower+codegen', ('lower', 'codegen', 'other'), 9000), ('optimizer', ('optimize',), 1000)]
HELLO_BUDGET_MS = 20.0
HELLO_GATED = True      # hello is under its 20 ms budget: a regression past it fails


def phase_totals(toolchain: Toolchain, sources: list[str],
                 lines_required: bool = True) -> tuple[dict[str, int], int, int | None] | None:
    """Each build --time phase's instructions (root, library and shared work alike), summed over sources, with
    their processed nodes and processed lines; None for a compiler without the phase split. The phase gate
    reads instructions and nodes only, so a base whose line counts are missing or negative still gates
    (its lines come back None); the candidate's must be usable (`lines_required`): a bad count fails loudly
    (ValueError, RuntimeError) instead of skipping the gate."""
    totals: dict[str, int] = {}
    nodes, lines = 0, 0
    for source in sources:
        report = time_run(toolchain, source)
        split = speed_corpus.instruction_split(report)
        count = speed_corpus.node_total(report)
        if not split or count is None or not any('optimize' in side for side in split.values()):
            return None
        nodes += count
        try:
            found = speed_corpus.processed(report)
        except ValueError:
            if lines_required:
                raise
            found = None
        if found is None and lines_required:
            raise RuntimeError(f'{source}: the candidate does not count processed lines')
        lines = lines + found['all'] if found and lines is not None else None
        for side in split.values():
            for phase, n in side.items():
                if phase != 'total':
                    totals[phase] = totals.get(phase, 0) + n
    return totals, nodes, lines


def cost_model(candidate: Toolchain, base: Toolchain | None, limit: float,
               skip: set[str] = frozenset()) -> list[tuple[str, float]]:
    """The flagship panel's instructions per processed node by phase, against the budgets; returns the phases
    that grew more than `limit` percent over the base's. Flagships in `skip` (the base measured an older copy of
    their source) are left out of the comparison with the base, never compared across different programs."""
    named = [(name, source) for name, source, _ in panel(False) if name.startswith('flagship ')]
    sources = [source for _, source in named]
    common = [source for name, source in named if name not in skip]
    new = phase_totals(candidate, sources)
    old = phase_totals(base, common, lines_required=False) if base is not None and common else None
    compared = phase_totals(candidate, common) if old and len(common) < len(sources) else new
    if new is None:
        print('  (no phase split: build --time needs Linux x86-64 hardware counters)')
        return []
    totals, nodes, lines = new
    assert lines is not None
    per_node = IPS / GOAL_LINES_PER_SECOND / NODES_PER_LINE
    print(f'cost model, flagship panel ({len(sources)} programs, {lines} processed lines, {nodes} processed nodes, '
          f'{nodes / lines:.1f} nodes/line; instructions per processed node, library and instance work included)'
          + ('' if old else ': no base phase split, not gated'))
    if old and len(common) < len(sources):
        print(f'  (base columns: {len(common)} of {len(sources)} programs; left out, measured on different sources: '
              + ', '.join(name for name, source in named if name in skip) + ')')
    print(f'  {"phase":16}{"budget":>8}{"now":>8}{"x budget":>9}{"k/line":>8}' + (f'{"base":>8}{"change":>9}' if old else ''))
    failures = []
    for row, parts, budget in PHASE_BUDGETS:
        n = sum(totals.get(p, 0) for p in parts)
        ratio = f'{n / nodes / (budget / NODES_PER_LINE):8.1f}x' if budget else ' ' * 9
        line = f'  {row:16}{round(budget / NODES_PER_LINE) if budget else "-":>8}{n / nodes:8.0f}{ratio}{n / lines / 1e3:8.1f}'
        if old:
            b = sum(old[0].get(p, 0) for p in parts)
            c = sum(compared[0].get(p, 0) for p in parts)
            change = round(delta(b, c), 2) + 0.0 if b else 0.0
            line += f'{b / old[1]:8.0f}{change:+8.2f}%'
            # (every phase is gated once: facts+effects is its two rows)
            if b and change > limit and row != 'facts+effects':
                failures.append((row, change))
                line += ' <-'
        print(line, flush=True)
    total = sum(totals.values())
    print(f'  {"total":16}{per_node:8.0f}{total / nodes:8.0f}{total / nodes / per_node:8.1f}x{total / lines / 1e3:8.1f}')
    print('  (budget: 250k processed lines/s at the reference rate, split by phase at 8 nodes a line)')
    return failures


def processed_report(toolchain: Toolchain, source: str, required: bool = True) -> dict | None:
    """The processed lines of one compile. A compiler that does not count them (or counts below nothing, as
    older bases did) gives None when not `required`; a required count that is unusable raises."""
    try:
        return speed_corpus.processed(time_run(toolchain, source))
    except ValueError:
        if required:
            raise
        return None


def yardstick(toolchain: Toolchain, counts: dict[str, int]) -> list[str]:
    """The candidate's latency and throughput, from its gated counts and one `build --time` per item; returns
    the hello gate's failure message, if it is gated and over."""
    print(f'compile yardstick ({toolchain.label}): est. ms and lines/s are instructions at {IPS / 1e9:.1f} G/s, the '
          'reference machine\'s single-thread compiler rate (compile_throughput.md), a load-independent proxy, not '
          'wall time. Throughput counts every processed line (code lines, comments and blanks left out): the '
          'program\'s ("user"), the library\'s that the compile reached (lazy bodies nobody asked for left out) and '
          'each generic instance\'s declaration once per instance. Fan-out = library + instance lines. The split '
          'into root, library (lib/, generic instances included) and shared work, and into phases, comes from '
          'build --time')
    rows = [(name, source) for name, source, flags in panel(False) if name not in ('self-build', 'game')]
    found = {}
    for name, source in rows:
        try:
            report = time_run(toolchain, source)
        except CompileError:
            print(f'  {name:30}(cannot build)')
            continue
        found[name] = (counts[name], speed_corpus.instruction_split(report) or {}, processed_report(toolchain, source))
    phases = ('load', 'check', 'facts', 'effects', 'ownership', 'lower', 'optimize', 'codegen')
    print(f'  latency {"":22}{"G inst":>9}{"est ms":>8}{"root M":>9}{"lib M":>9}{"shared M":>9}{"lib lines":>10}{"inst lines":>11}'
          '   library M by phase')
    failures = []
    for name, (inst, split, lines) in found.items():
        if name.startswith('flagship ') or name.startswith('synthetic'):
            continue
        sides = ''.join(f'{split[k]["total"] / 1e6:9.1f}' if k in split else f'{"-":>9}'
                        for k in ('root', 'library', 'shared'))
        detail = ', '.join(f'{k} {v / 1e6:.1f}' for k, v in split.get('library', {}).items() if k != 'total')
        fan = f'{lines["library"]:10}{lines["instance"]:11}' if lines else f'{"-":>10}{"-":>11}'
        print(f'    {name:28}{inst / 1e9:9.4f}{inst / IPS * 1e3:8.1f}{sides}{fan}   {detail}', flush=True)
        if name == 'hello':
            ms = inst / IPS * 1e3
            over = ms > HELLO_BUDGET_MS
            print(f'    hello latency {ms:.1f} ms against the {HELLO_BUDGET_MS:.0f} ms budget: '
                  + ('within' if not over else 'over, gated' if HELLO_GATED else 'over (reported, not gated yet)'))
            if over and HELLO_GATED:
                failures.append(f'hello latency is {ms:.1f} ms (budget {HELLO_BUDGET_MS:.0f} ms)')
    floor = found.get('hello', (0,))[0]
    print(f'  throughput {"":10}{"user":>6}{"all":>7}{"lib":>7}{"inst":>6}{"G inst":>8}{"est ms":>7}{"lines/s":>9}{"user/s":>8}'
          f'{"k/line":>7}{">hello":>7}   k inst per processed line: ' + ' '.join(f'{p[:5]:>6}' for p in phases))
    total = {'user': 0, 'all': 0, 'library': 0, 'instance': 0, 'inst': 0}
    by_phase = {p: 0 for p in phases}

    def row(name: str, lines: dict, inst: int, phased: dict, count: int) -> None:
        above = (inst - count * floor) / lines['all'] / 1e3
        seconds = inst / IPS
        print(f'    {name:20}{lines["root"]:6}{lines["all"]:7}{lines["library"]:7}{lines["instance"]:6}{inst / 1e9:8.4f}'
              f'{seconds * 1e3:7.1f}{lines["all"] / seconds:9.0f}{lines["root"] / seconds:8.0f}'
              f'{inst / lines["all"] / 1e3:7.1f}{above:7.1f}   {"":25}'
              + ' '.join(f'{phased.get(p, 0) / lines["all"] / 1e3:6.1f}' for p in phases), flush=True)
    flagships = 0
    for name, (inst, split, lines) in found.items():
        if not (name.startswith('flagship ') or name.startswith('synthetic')):
            continue
        if not lines:
            print(f'    {name:20}(this compiler does not count processed lines)')
            continue
        phased = {p: sum(side.get(p, 0) for side in split.values()) for p in phases}
        row(name.replace('flagship ', ''), lines, inst, phased, 1)
        if name.startswith('flagship '):
            flagships += 1
            total['inst'] += inst
            for key in ('all', 'library', 'instance'):
                total[key] += lines[key]
            total['user'] += lines['root']
            for p in phases:
                by_phase[p] += phased[p]
    if flagships:
        row('flagships (sum)', {'root': total['user'], 'all': total['all'], 'library': total['library'],
                                'instance': total['instance']}, total['inst'], by_phase, flagships)
        print(f'    flagship fan-out {(total["library"] + total["instance"]) / total["user"]:.1f} library + instance lines '
              f'per user line; goal {GOAL_LINES_PER_SECOND // 1000}k processed lines/s single-thread')
    return failures


def throughput_gate(candidate: Toolchain, base: Toolchain | None, counts: dict[str, int],
                    base_counts: dict[str, int], limit: float, counters: bool = True,
                    skip: set[str] = frozenset()) -> list[str]:
    """The flagship panel's all-lines throughput against the base's: a drop of more than `limit` percent in
    processed lines per instruction fails unless the panel also got cheaper (a fan-out cut that pays for
    itself). A base that does not count lines cannot be compared. Flagships in `skip` (the base measured an older
    copy of their source) are left out of the comparison: two different programs have no rate to compare."""
    names = [name for name, _, _ in panel(False) if name.startswith('flagship ')]
    sources = {name: source for name, source, _ in panel(False)}
    new_lines = [processed_report(candidate, sources[n]) for n in names]
    if any(x is None for x in new_lines):
        if not counters:
            # (build --time counts lines and nodes only with hardware counters, which CI's virtual machines lack)
            print('throughput gate: no hardware counters on this host, so no processed lines; not gated here')
            return []
        raise RuntimeError('the candidate does not count processed lines: the throughput gate cannot run')
    if base is None:
        return []
    if skip & set(names):
        print('throughput gate: left out of the comparison (the base measured an older copy of the source): '
              + ', '.join(sorted(skip & set(names))))
        keep = [i for i, n in enumerate(names) if n not in skip]
        names, new_lines = [names[i] for i in keep], [new_lines[i] for i in keep]
        if not names:
            return []
    old_lines = [processed_report(base, sources[n], required=False) for n in names]
    if any(x is None for x in old_lines) or any(n not in base_counts for n in names):
        print('throughput gate: the base does not count processed lines; not gated this time')
        return []
    new_inst, old_inst = sum(counts[n] for n in names), sum(base_counts[n] for n in names)
    new_rate = sum(x['all'] for x in new_lines) / new_inst * IPS
    old_rate = sum(x['all'] for x in old_lines) / old_inst * IPS
    change = round(delta(old_rate, new_rate), 2) + 0.0
    cheaper = new_inst < old_inst
    over = change < -limit and not cheaper
    print(f'throughput gate, flagships (all processed lines/s at {IPS / 1e9:.1f} G/s): {old_rate:.0f} -> {new_rate:.0f}  '
          f'{change:+.2f}% (instructions {delta(old_inst, new_inst):+.2f}%)' + (' <-' if over else ''))
    return [f'flagship all-lines throughput needs {-change:+.2f}% processed lines/s vs base (limit {limit}%) and the panel got no cheaper'] if over else []


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
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'), DEWY_EMIT_WORKERS=str(workers))
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
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'), DEWY_EMIT_WORKERS=str(workers))
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


def corpus_processed(active: Path, program: Path) -> dict:
    """The lines and nodes `build --time` says the candidate processed compiling the program."""
    env = clean_env(DEWY_CORE_LIB=str(active / 'lib'))
    run = subprocess.run([active / 'bin/dewy-core', 'build', program, '--time', '-o', active / 'program'],
                         cwd=ROOT, env=env, capture_output=True, text=True)
    if run.returncode:
        raise CompileError(run.stdout + run.stderr)
    found = speed_corpus.processed(run.stderr)
    if found is None:
        raise RuntimeError(f'{program}: the candidate does not count processed lines')
    return found


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
    hello = Path(hello_source())
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
        found = [corpus_processed(staged['candidate'], program) for program in kept]
        user = sum(item['root'] for item in found)
        lines = sum(item['all'] for item in found)
        library = sum(item['library'] for item in found)
        instance = sum(item['instance'] for item in found)
        print(f'  {name}: {len(kept)} programs, {lines} processed lines ({user} user, {library} library reached, '
              f'{instance} generic instance; fan-out {(library + instance) / user:.1f} per user line; '
              f'{sum(item["nodes"] for item in found)} nodes; summed over compiles)')
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
            line += f'   {new / lines / 1e3:7.1f} k inst/processed line ({net / lines / 1e3:.1f} net of hello)'
            if args.wall:
                ms = walls[n]
                line += f'   {lines / ms["candidate"] * 1e3:9.0f} lines/s ({user / ms["candidate"] * 1e3:.0f} user)'
                if 'base' in ms:
                    line += f' (base {lines / ms["base"] * 1e3:.0f})'
            elif n == 1:
                line += f'   est. {lines / (new / IPS):9.0f} lines/s ({user / (new / IPS):.0f} user)'
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
    headless.activate()
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
    cli.add_argument('--cycles', action='store_true', help='report pinned interleaved hardware cycles and instructions')
    cli.add_argument('--cpu', type=int, help='--cycles: required allowed logical CPU; keep its SMT sibling idle')
    args = cli.parse_args(argv)
    if args.cycles:
        if args.cpu is None or not hasattr(os, 'sched_getaffinity') or args.cpu not in os.sched_getaffinity(0):
            cli.error('--cycles requires --cpu naming an allowed Linux CPU')
        if args.runs < 15:
            cli.error('--cycles requires --runs >= 15')
        if args.wall or args.critical or args.corpus or args.no_pin or args.checkpoint or args.counter == 'valgrind':
            cli.error('--cycles cannot combine with wall/critical/corpus/no-pin/checkpoint/valgrind')
        from tools.compiler.speed_cycles import report
        return report(args, current)
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
        counts = {}
        base_counts = {}
        fallbacks: list[Fallback] = []
        drifts: list[Drift] = []
        for name, source, flags in panel(args.release):
            new = measure(counter, candidate, source, flags, notes)
            counts[name] = new
            line = f'  {name:26}'
            found, drifted = [], []
            for role, (revision, _, toolchain) in references.items():
                old, own = measure_item(counter, toolchain, source, flags)
                if role == 'base':
                    base_counts[name] = old
                prefix = '' if role == 'base' else f'   {revision}'
                if own is not None:
                    # (a different program on the base's side: the percentage would be meaningless, and the
                    # base's old copy must never stand in for this source unannounced)
                    try:
                        same = measure(counter, candidate, str(own), flags, [])
                    except RuntimeError:
                        same = None
                    fb = Fallback(role, name, toolchain.label.split()[-1], old, new, same)
                    found.append(fb)
                    if fb.compiler is not None and fb.compiler > args.limit:
                        failures.append((role, f'{name} (compiler alone, on {role}\'s source)', fb.compiler))
                    line += f'{prefix} {old / 1e9:8.4f} -> {new / 1e9:8.4f}  {"DIFFERENT SOURCE":>16} <-'
                    continue
                change = round(delta(old, new), 2) + 0.0
                over = change > args.limit
                if over:
                    failures.append((role, name, change))
                line += f'{prefix} {old / 1e9:8.4f} -> {new / 1e9:8.4f}  {change:+6.2f}%' + (' <-' if over else '   ')
                if source_drifted(toolchain.inputs, source):
                    # (the same source on both sides hides the program's own growth: measure the candidate on
                    # the reference's copy too, only for programs whose files changed)
                    try:
                        same = measure(counter, candidate, str(toolchain.inputs / source), flags, [])
                    except RuntimeError:
                        same = None
                    drifted.append(Drift(role, name, toolchain.label.split()[-1], old, new, same))
            print(line.rstrip(), flush=True)
            for fb in found:
                for text in fb.lines():
                    print(text, flush=True)
            for d in drifted:
                for text in d.lines():
                    print(text, flush=True)
            fallbacks += found
            drifts += drifted
        source_row(counter, candidate, references['base'][2], counts, notes, max(args.limit, SOURCE_LIMIT), failures)
        for note in dict.fromkeys(notes):
            print(f'  ({note})')
        hello_failures = yardstick(candidate, counts)
        base_toolchain = references['base'][2]
        mixed = {fb.name for fb in fallbacks if fb.role == 'base'}
        throughput_failures = throughput_gate(candidate, base_toolchain, counts, base_counts, args.limit,
                                             counter.kind == 'perf', skip=mixed)
        for row, change in cost_model(candidate, base_toolchain, args.limit, skip=mixed):
            failures.append(('base', f'phase {row} (flagships)', change))
        print(f'  ({time.perf_counter() - started:.0f} s)')
    ranges = {role: accepted(git('log', '--format=%B', f'{commit}..HEAD')) for role, (_, commit, _) in references.items()}
    fallback_failures, growth_accepted = fallback_verdict(fallbacks, args.limit, ranges)
    drift_failures, drift_accepted = drift_verdict(drifts, args.limit, ranges)
    growth_accepted += drift_accepted
    for text in growth_accepted:
        print(f'speed: source growth accepted for {text}')
    base_failures = [f for f in failures if f[0] == 'base']
    other_failures = [f for f in failures if f[0] != 'base']
    if (base_failures or throughput_failures) and reasons:
        print('speed: base regression accepted: ' + '; '.join(reasons))
        base_failures, throughput_failures = [], []
    remaining = base_failures + other_failures
    for role, name, change in remaining:
        print(f'speed: {name} needs {change:+.2f}% instructions vs {role} (limit {args.limit}%)', file=sys.stderr)
    for message in throughput_failures + hello_failures:
        print(f'speed: {message}', file=sys.stderr)
    for message in fallback_failures:
        print(f'speed: FALLBACK {message}', file=sys.stderr)
    if fallback_failures:
        print('speed: the base could not build that source, so its cost never reached a comparison: add a line '
              '`speed: accept <reason naming the program>` to a commit message since then, or change the source',
              file=sys.stderr)
    for message in drift_failures:
        print(f'speed: SOURCE DRIFT {message}', file=sys.stderr)
    if drift_failures:
        print('speed: both compilers ran on this source, so the program\'s own growth is no compiler cost: add a line '
              '`speed: accept <reason naming the program>` to a commit message since then, or trim the source',
              file=sys.stderr)
    if remaining or throughput_failures:
        print('speed: add a line `speed: accept <reason>` to the commit message when the cost is intended',
              file=sys.stderr)
    return 1 if remaining or throughput_failures or hello_failures or fallback_failures or drift_failures else 0
