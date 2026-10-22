"""Differential fuzzing of generated Dewy programs against an independent oracle.

    python3 -m tools.core fuzz [--seed N] [--count N] [--minutes M] [--modes ...]

Each seed yields a typed Dewy program (tools/compiler/dewy_fuzz_programs.py)
plus metamorphic variants that must print the same output: an identity copy,
reordered independent statements, an outlined helper and a loop rewritten as a
comprehension. The Python oracle supplies the expected stdout. Programs compile
together as modules of one program per mode (native and web, default and
release); a failure is rebuilt alone to confirm it, then shrunk. Minimized
failures go to build/dewy-fuzz-failures/ (untracked).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from tools import cases
from tools.compiler import dewy_fuzz_programs as gen

MODES = ('native', 'native-release', 'web', 'web-release')
MARK = '@@dewy-fuzz@@'
FAILURES = Path(__file__).resolve().parents[2] / 'build' / 'dewy-fuzz-failures'
SCRATCH = Path.home() / 'dev' / 'tmp' / 'dewy-fuzz-work'
RUN_TIMEOUT = 20


@dataclass
class Case:
    seed: int
    variant: str
    program: gen.Program
    expected: str
    exit: int = 0  # 101: a checked failure (an `int` overflow) ends the program
    path: Path | None = None

    @property
    def name(self) -> str:
        return f'seed{self.seed}-{self.variant}'


@dataclass
class Failure:
    case: Case
    mode: str
    kind: str          # reject, crash, mismatch, batch-only or variant (an oracle-side bug)
    detail: str
    actual: str = ''
    signature: tuple = ()


@dataclass
class Stats:
    programs: int = 0
    variants: int = 0
    discarded: int = 0
    builds: int = 0
    runs: int = 0
    failures: list[Failure] = field(default_factory=list)


def make_cases(seed: int, features=None) -> tuple[list[Case], int, list[Failure]]:
    program, discarded = gen.generate(seed, features)
    expected, exit = program.outcome()
    found = [Case(seed, 'original', program, expected, exit)]
    problems = []
    for name, variant in gen.variants(program, seed).items():
        try:
            outcome = variant.outcome()
            errors = gen.scope_errors(variant)
        except gen.InvalidProgram as error:
            outcome, errors = None, [str(error)]
        case = Case(seed, name, variant, expected, exit)
        if outcome != (expected, exit) or errors:
            problems.append(Failure(case, 'oracle', 'variant', f'the {name} transform changed the oracle outcome '
                                    f'or scoping: {errors[:3]}', outcome[0] if outcome else ''))
            continue
        found.append(case)
    return found, discarded, problems


def normalize(message: str) -> str:
    """An error message without generated names or numbers, to compare failures."""
    return re.sub(r'\d+', 'N', re.sub(r'\b[a-z]+\d+\b', 'X', message))


def first_error(text: str) -> str:
    for line in text.splitlines():
        if ': error: ' in line:
            return line.split(': error: ', 1)[1].strip()
    return text.strip().splitlines()[-1] if text.strip() else 'build failed'


class Fuzzer:
    def __init__(self, compiler: Path, modes, workers: int, scratch: Path):
        node = shutil.which('node')
        if node is None and any(m.startswith('web') for m in modes):
            raise RuntimeError('web modes need Node; pass --modes native native-release')
        self.modes = tuple(modes)
        self.workers = workers
        self.scratch = scratch
        self.runner = cases.Runner(compiler, scratch, cases.clean_environment(), node)

    # Single programs -----------------------------------------------------------

    def outcome(self, program: gen.Program, mode: str, expected: str, exit: int = 0):
        """('pass'|'reject'|'crash'|'mismatch', detail, actual) for one program alone."""
        work = self.runner.directory('single')
        source = work / 'program.dewy'
        source.write_text(program.source())
        output = work / 'program'
        built = self.runner.build(source, output, mode)
        if built.returncode:
            text = built.stdout + built.stderr
            if exit == 101 and re.search(r'error: (integer overflow|\S+ does not fit)', text):
                return 'pass', '', text  # a provable overflow may be reported while compiling
            return 'reject', first_error(text), text
        code, stdout, stderr = self.runner.execute(self.runner.command(output, mode), timeout=RUN_TIMEOUT)
        if code != exit:
            return 'crash', f'exit {code}' + (f', expected {exit}' if exit else ''), stdout + stderr
        if stdout != expected:
            return 'mismatch', 'stdout differs from the oracle', stdout
        return 'pass', '', stdout

    @staticmethod
    def signature(kind, detail):
        return (kind, normalize(detail)) if kind in ('reject', 'crash') else (kind,)

    # Batches -------------------------------------------------------------------

    def driver(self, batch: list[Case]) -> str:
        lines = [f'from p"{c.path.as_posix()}" import (main as case_{i})' for i, c in enumerate(batch)]
        lines.append('main=():>void=>{')
        for i in range(len(batch)):
            lines += [f'    printl"{MARK}B{i}"', f'    case_{i}()', f'    printl"{MARK}E{i}"']
        lines.append('}')
        return '\n'.join(lines) + '\n'

    def run_batch(self, batch: list[Case], mode: str) -> list[Failure]:
        """Compile the cases as modules of one program, run it once and judge each case."""
        failures = []
        batch = list(batch)
        while batch:
            work = self.runner.directory(mode)
            (work / 'batch.dewy').write_text(self.driver(batch))
            output = work / 'batch'
            built = self.runner.build(work / 'batch.dewy', output, mode)
            if built.returncode == 0:
                break
            text = built.stdout + built.stderr
            culprit = self.locate(text, batch)
            if culprit is None:
                # Unattributable: judge each case alone.
                return failures + [f for c in batch for f in self.confirm(c, mode, 'reject', first_error(text))]
            failures += self.confirm(batch.pop(culprit), mode, 'reject', first_error(text))
        if not batch:
            return failures
        code, stdout, stderr = self.runner.execute(self.runner.command(output, mode), timeout=RUN_TIMEOUT * 3)
        results, started = parse(stdout)
        for i, case in enumerate(batch):
            if i in results:
                if results[i] != case.expected:
                    failures += self.confirm(case, mode, 'mismatch', 'stdout differs from the oracle')
            else:
                # The first case without a result ended the process: judge it alone, resume after it.
                failures += self.confirm(case, mode, 'crash', f'exit {code} (case {started} was running)')
                rest = [c for j, c in enumerate(batch) if j > i]
                return failures + (self.run_batch(rest, mode) if rest else [])
        if code != 0 and len(results) == len(batch):
            failures.append(Failure(batch[-1], mode, 'batch-only', f'batch exited {code} after every case',
                                    cases.tail(stdout + stderr)))
        return failures

    def locate(self, text: str, batch: list[Case]) -> int | None:
        match = cases.ERROR.search(text)
        if match is None:
            return None
        path = Path(match[1])
        for i, case in enumerate(batch):
            if path.name == case.path.name and path.resolve() == case.path.resolve():
                return i
        return None

    def single(self, case: Case, mode: str) -> list[Failure]:
        kind, detail, actual = self.outcome(case.program, mode, case.expected, case.exit)
        return [] if kind == 'pass' else [Failure(case, mode, kind, detail, actual, self.signature(kind, detail))]

    def confirm(self, case: Case, mode: str, kind: str, detail: str) -> list[Failure]:
        """Rebuild a case alone; a failure that disappears is reported as batch-only."""
        alone, alone_detail, actual = self.outcome(case.program, mode, case.expected, case.exit)
        if alone == 'pass':
            return [Failure(case, mode, 'batch-only', f'{kind} ({detail}) only inside a batch')]
        return [Failure(case, mode, alone, alone_detail, actual, self.signature(alone, alone_detail))]

    # Shrinking -------------------------------------------------------------------

    def shrink(self, failure: Failure, budget: float, tests: int = 600) -> gen.Program:
        current = failure.case.program
        deadline = time.monotonic() + budget
        tried = 0
        progress = True
        while progress and time.monotonic() < deadline and tried < tests:
            progress = False
            current_size = gen.size(current)
            for candidate in gen.reductions(current):
                if time.monotonic() >= deadline or tried >= tests:
                    break
                if gen.size(candidate) >= current_size or not gen.valid(candidate):
                    continue
                tried += 1
                kind, detail, _ = self.outcome(candidate, failure.mode, *candidate.outcome())
                if kind == failure.kind and self.signature(kind, detail) == failure.signature:
                    current = candidate
                    progress = True
                    break
        return current

    def save(self, group: list[Failure], program: gen.Program, root: Path) -> Path:
        failure = group[0]
        case = failure.case
        target = root / f'{failure.kind}-seed{case.seed}'
        number = 1
        while target.exists() and (target / 'signature').read_text() != repr(failure.signature or failure.detail):
            number += 1
            target = root / f'{failure.kind}-seed{case.seed}-{number}'
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        (target / 'signature').write_text(repr(failure.signature or failure.detail))
        (target / 'program.dewy').write_text(program.source())
        (target / 'unshrunk.dewy').write_text(case.program.source())
        expected, exit = program.outcome() if failure.kind != 'variant' else (case.expected, case.exit)
        (target / 'expected.out').write_text(expected)
        kind, detail, actual = (failure.kind, failure.detail, failure.actual)
        if failure.mode in MODES and failure.kind in ('reject', 'crash', 'mismatch'):
            kind, detail, actual = self.outcome(program, failure.mode, expected, exit)
        (target / 'actual.out').write_text(actual)
        flags = ' '.join(self.runner.flags(failure.mode)) if failure.mode in MODES else ''
        variants = sorted({f.case.variant for f in group})
        modes = [m for m in (*MODES, 'oracle') if any(f.mode == m for f in group)]
        (target / 'info.txt').write_text(
            f'{failure.kind} in {failure.mode}: {failure.detail}\n'
            f'seed {case.seed}; variants: {" ".join(variants)}; modes: {" ".join(modes)}\n'
            f'expected exit {exit}' + (' (or a compile-time integer overflow error)' if exit == 101 else '') + '\n'
            f'program.dewy ({case.variant}, {"minimized" if program is not case.program else "not minimized"}): '
            f'{kind} ({detail})\n'
            f'reproduce: dewy-core build program.dewy -o program {flags}\n'
            f'regenerate: python3 -m tools.core fuzz --seed {case.seed} --count 1\n')
        return target


def parse(stdout: str) -> tuple[dict[int, str], int | None]:
    results, started, position = {}, None, 0
    begin = re.compile(re.escape(MARK) + r'B(\d+)\n')
    while (opened := begin.search(stdout, position)) is not None:
        index = int(opened[1])
        started = index
        end = stdout.find(f'{MARK}E{index}\n', opened.end())
        if end < 0:
            break
        results[index] = stdout[opened.end():end]
        position = end
    return results, started


def fuzz(compiler: Path, *, seed: int = 1, count: int | None = None, minutes: float | None = None,
         modes=MODES, workers: int = 2, batch_size: int = 8, shrink: int = 6, failures_dir: Path = FAILURES,
         features=None, quiet: bool = False, work: Path = SCRATCH) -> int:
    started = time.monotonic()
    if count is None and minutes is None:
        count = 50
    deadline = started + minutes * 60 if minutes is not None else None
    work.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix='run-', dir=work))
    fuzzer = Fuzzer(compiler, modes, workers, scratch)
    stats = Stats()
    number = seed
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers))
    try:
        while (count is None or number < seed + count) and (deadline is None or time.monotonic() < deadline):
            batch = []
            last = number + batch_size if count is None else min(number + batch_size, seed + count)
            for s in range(number, last):
                try:
                    made, discarded, problems = make_cases(s, features)
                except gen.InvalidProgram:
                    stats.discarded += 25
                    continue
                stats.programs += 1
                stats.variants += len(made) - 1
                stats.discarded += discarded
                stats.failures += problems
                directory = scratch / f'seed{s}'
                directory.mkdir()
                for case in made:
                    case.path = directory / f'{case.variant}.dewy'
                    case.path.write_text(case.program.source())
                batch += made
            number = last
            # Cases expected to fail stop a process early: they run alone.
            singles = [c for c in batch if c.exit]
            batch = [c for c in batch if not c.exit]
            futures = [pool.submit(fuzzer.run_batch, batch, mode) for mode in modes]
            futures += [pool.submit(fuzzer.single, case, mode) for case in singles for mode in modes]
            for future in futures:
                stats.failures += future.result()
            if not quiet:
                found = len(stats.failures)
                print(f'fuzz: seeds {seed}..{number - 1}, {found} failure(s), {time.monotonic() - started:.0f} s',
                      file=sys.stderr, flush=True)
    finally:
        pool.shutdown()
    elapsed = time.monotonic() - started
    saved = []
    groups: dict[tuple, list[Failure]] = {}
    for failure in stats.failures:
        detail = failure.case.variant if failure.kind == 'variant' else failure.signature or failure.detail
        groups.setdefault((failure.case.seed, failure.kind, detail), []).append(failure)
    if groups:
        failures_dir.mkdir(parents=True, exist_ok=True)
        shrunk = set()
        for group in groups.values():
            # Minimize the plainest member: the original program, in the cheapest mode.
            group.sort(key=lambda f: (f.case.variant != 'original', MODES.index(f.mode) if f.mode in MODES else 0))
            failure, program = group[0], group[0].case.program
            if failure.kind in ('reject', 'crash', 'mismatch') and len(shrunk) < shrink \
                    and failure.signature not in shrunk:
                shrunk.add(failure.signature)
                program = fuzzer.shrink(failure, budget=90)
            saved.append(fuzzer.save(group, program, failures_dir))
    builds, runs = fuzzer.runner.builds, fuzzer.runner.runs
    kinds = {}
    for kind, *_ in (key[1:] for key in groups):
        kinds[kind] = kinds.get(kind, 0) + 1
    detail = ', '.join(f'{n} {k}' for k, n in sorted(kinds.items()))
    print(f'fuzz: {stats.programs} programs (+{stats.variants} variants, {stats.discarded} discarded) from seed {seed}, '
          f'{len(modes)} modes, {builds} builds, {runs} runs: {len(groups)} failure(s)'
          + (f' ({detail})' if detail else '') + f' in {elapsed:.0f} s, {stats.programs / max(elapsed, 1e-9):.2f} programs/s'
          + (f'; see {failures_dir}' if saved else ''), flush=True)
    shutil.rmtree(scratch, ignore_errors=True)
    return 1 if stats.failures else 0


def arguments(argv):
    cli = argparse.ArgumentParser(prog='python3 -m tools.core fuzz', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--seed', type=int, default=1, help='first seed (default 1)')
    cli.add_argument('--count', type=int, help='number of seeds (default 50 unless --minutes is given)')
    cli.add_argument('--minutes', type=float, help='stop starting new batches after this long')
    cli.add_argument('--modes', nargs='+', choices=MODES, default=list(MODES))
    cli.add_argument('-n', '--workers', type=int, default=2, help='parallel builds/runs (default 2)')
    cli.add_argument('--batch', type=int, default=8, help='seeds compiled together per build (default 8)')
    cli.add_argument('--shrink', type=int, default=6, help='distinct failures to minimize (default 6)')
    cli.add_argument('--features', nargs='+', choices=gen.FEATURES, help='restrict the generated features')
    cli.add_argument('--work', type=Path, default=SCRATCH, help='scratch directory for builds and runs')
    cli.add_argument('--failures', type=Path, default=FAILURES, help=f'failure directory (default {FAILURES})')
    cli.add_argument('--compiler', type=Path, help='use this compiler instead of the cached build')
    cli.add_argument('--print', dest='show', action='store_true', help='print the seed\'s program and oracle output')
    cli.add_argument('-q', '--quiet', action='store_true', help='only the summary line')
    return cli.parse_args(argv)


def main(argv=None, compiler: Path | None = None) -> int:
    options = arguments(argv)
    if options.show:
        program, _ = gen.generate(options.seed, options.features)
        print(program.source() + '\n# oracle output:\n' + program.expected(), end='')
        return 0
    compiler = options.compiler or compiler
    if compiler is None:
        print('fuzz: pass --compiler or run through python3 -m tools.core fuzz', file=sys.stderr)
        return 2
    try:
        return fuzz(Path(compiler).resolve(), seed=options.seed, count=options.count, minutes=options.minutes,
                    modes=options.modes, workers=options.workers, batch_size=options.batch, shrink=options.shrink,
                    failures_dir=options.failures.expanduser().resolve(), features=options.features,
                    quiet=options.quiet, work=options.work.expanduser().resolve())
    except RuntimeError as error:
        print(f'fuzz: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
