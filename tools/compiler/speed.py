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
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / '__dewycache__' / 'speed'
COUNTER_SOURCE = Path(__file__).with_name('count_instructions.c')
GAME = 'examples/dunes.dewy'
SYNTHETIC_FUNCTIONS = 1000
STABLE = 1e-4          # two runs of one item must agree within 0.01%
KEEP_BASES = 16        # cached base compilers kept (most recently used)
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
    parts.append('let items:array<Item>=[]\nloop i in [0..100) {items.push(Item[x=f64(i) y=f64(i)*0.5 id=i])}\nlet acc:float64=0.0')
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
    env.update(SLOPPY_EMIT_WORKERS='1', **extra)
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


def resolve(revision: str) -> str:
    return git('rev-parse', '--verify', f'{revision}^{{commit}}')


def main(argv: list[str], current: Path) -> int:
    cli = argparse.ArgumentParser(prog='python3 -m tools.core speed', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--base', default='HEAD~1', help='commit to compare with (default HEAD~1)')
    cli.add_argument('--checkpoint', metavar='TAG', help='also compare with this fixed revision, e.g. speed-checkpoint')
    cli.add_argument('--limit', type=float, default=1.0, help='allowed increase in percent (default 1.0)')
    cli.add_argument('--release', action='store_true', help='also measure release builds')
    cli.add_argument('--counter', choices=('auto', 'perf', 'valgrind'), default='auto')
    args = cli.parse_args(argv)
    started = time.perf_counter()
    CACHE.mkdir(parents=True, exist_ok=True)
    with (CACHE / 'speed.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
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
