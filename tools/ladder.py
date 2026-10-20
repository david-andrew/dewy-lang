"""Score the acceptance ladder in tests/ladder (see ROADMAP.md).

    python3 -m tools.core ladder [-k WORDS] [-n N] [--update-ratchet]

Each program has `design.dewy` (the design surface), `core.dewy` (today's
accepted dialect) and `expected.out` from the oracles in references.py. A
version passes when it checks, builds (native, release), exits 0 and prints
exactly the expected output. The command fails when a core version fails or a
design program listed in ladder.json's "design_passing" ratchet stops passing.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from tools.cases import ROOT, clean_environment, default_workers, keyword_filter

LADDER = ROOT / 'tests' / 'ladder'
RUN_TIMEOUT = 30


@dataclass
class Result:
    program: str
    version: str
    ok: bool
    checked: bool
    error: str = ''


def first_error(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    line = next((line for line in lines if 'error' in line.lower()), lines[0] if lines else '(no output)')
    return line.replace(str(LADDER) + os.sep, '')


def evaluate(compiler: Path, directory: Path, version: str, scratch: Path, env: dict) -> Result:
    source = directory / f'{version}.dewy'
    work = Path(tempfile.mkdtemp(prefix=f'{directory.name}-{version}-', dir=scratch))

    def step(command, timeout=120):
        try:
            return subprocess.run(command, cwd=work, env=env, capture_output=True, text=True,
                                  errors='replace', timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(command, 'timeout', '', f'timed out after {timeout} s')

    checked = step([str(compiler), 'check', str(source)])
    if checked.returncode != 0:
        return Result(directory.name, version, False, False, first_error(checked.stderr + checked.stdout))
    binary = work / 'program'
    built = step([str(compiler), 'build', str(source), '--release', '-o', str(binary)])
    if built.returncode != 0:
        return Result(directory.name, version, False, True, first_error(built.stderr + built.stdout))
    if not binary.exists() and binary.with_suffix('.exe').exists():
        binary = binary.with_suffix('.exe')
    ran = step([str(binary)], RUN_TIMEOUT)
    expected = (directory / 'expected.out').read_text()
    if ran.returncode != 0:
        detail = first_error(ran.stderr + ran.stdout) if (ran.stderr + ran.stdout).strip() else ''
        return Result(directory.name, version, False, True, f'exit {ran.returncode} {detail}'.strip())
    if ran.stdout != expected:
        return Result(directory.name, version, False, True,
                      f'printed {ran.stdout.strip()[:120]!r}, expected {expected.strip()[:120]!r}')
    return Result(directory.name, version, True, True)


@contextlib.contextmanager
def port_lock():
    """Networking programs use fixed loopback ports; serialize them machine-wide."""
    try:
        import fcntl
    except ImportError:
        yield
        return
    with open(Path(tempfile.gettempdir()) / 'dewy-ladder-ports.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def load() -> dict:
    return json.loads((LADDER / 'ladder.json').read_text())


def dump(doc: dict):
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    # One program per line keeps the mapping readable and diffs small.
    text = re.sub(r'\{\n\s+("milestone": \d+)(?:,\n\s+("serial": true))?\n\s+\}',
                  lambda m: '{' + m[1] + (', ' + m[2] if m[2] else '') + '}', text)
    (LADDER / 'ladder.json').write_text(text + '\n')


def validate(doc: dict) -> list[str]:
    problems = []
    directories = sorted(p.name for p in LADDER.iterdir() if p.is_dir() and p.name[:2].isdigit())
    if sorted(doc['programs']) != directories:
        problems.append('ladder.json programs and tests/ladder directories differ')
    for name in directories:
        for required in ('design.dewy', 'core.dewy', 'expected.out'):
            if not (LADDER / name / required).exists():
                problems.append(f'{name} lacks {required}')
    for name, entry in doc['programs'].items():
        if str(entry.get('milestone')) not in doc['milestones']:
            problems.append(f'{name} needs a milestone from 1 to {len(doc["milestones"])}')
    return problems


def run(compiler: Path, *, keyword: str = '', workers: int = 2, update_ratchet: bool = False,
        scoreboard: bool = True, json_output: Path | None = None) -> int:
    started = time.perf_counter()
    doc = load()
    problems = validate(doc)
    if problems:
        print('ladder: ' + '\nladder: '.join(problems), file=sys.stderr)
        return 2
    selected = keyword_filter(keyword)
    names = [name for name in doc['programs'] if selected(name)]
    if not names:
        print('ladder: no programs selected', file=sys.stderr)
        return 0
    scratch = Path(tempfile.mkdtemp(prefix='dewy-ladder-'))
    env = clean_environment()
    env['SLOPPY_THREADS'] = '2'
    jobs = [(name, version) for name in names for version in ('design', 'core')]
    parallel = [job for job in jobs if not doc['programs'][job[0]].get('serial')]
    serial = [job for job in jobs if doc['programs'][job[0]].get('serial')]
    results: dict[tuple[str, str], Result] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(evaluate, compiler, LADDER / n, v, scratch, env): (n, v) for n, v in parallel}
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    if serial:
        with port_lock():
            for name, version in serial:
                results[name, version] = evaluate(compiler, LADDER / name, version, scratch, env)
    shutil.rmtree(scratch, ignore_errors=True)

    design = {n: results[n, 'design'] for n in names}
    core = {n: results[n, 'core'] for n in names}
    ratchet = set(doc['design_passing'])
    regressed = sorted(n for n in names if n in ratchet and not design[n].ok)
    core_failed = sorted(n for n in names if not core[n].ok)
    newly = sorted(n for n in names if design[n].ok and n not in ratchet)
    elapsed = time.perf_counter() - started

    if json_output is not None:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        payload = {
            'schema': 1, 'revision': revision,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'host': f'{sys.platform}-{platform.machine()}', 'target': 'native-release',
            'milestones': doc['milestones'],
            'results': [dict(asdict(results[n, v]), milestone=doc['programs'][n]['milestone'])
                        for n, v in jobs],
        }
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2) + '\n')

    if scoreboard:
        print_scoreboard(doc, names, design, core)
    else:
        print(f'ladder: design {sum(r.ok for r in design.values())}/{len(names)}, '
              f'core {sum(r.ok for r in core.values())}/{len(names)} in {elapsed:.1f} s', flush=True)
    for name in core_failed:
        print(f'FAIL ladder {name} core: {core[name].error}')
    for name in regressed:
        print(f'FAIL ladder {name} design (listed in design_passing): {design[name].error}')
    if newly:
        if update_ratchet:
            doc['design_passing'] = sorted(ratchet | set(newly))
            dump(doc)
            print('ladder: added to design_passing: ' + ', '.join(newly))
        else:
            print('ladder: newly passing design programs (record with --update-ratchet): ' + ', '.join(newly))
    if scoreboard:
        print(f'ladder: {elapsed:.1f} s', flush=True)
    return 1 if core_failed or regressed else 0


def print_scoreboard(doc: dict, names: list[str], design: dict, core: dict):
    print('Acceptance ladder (native release builds)')
    print(f'  {"milestone":<40} {"design":>8} {"core":>8}')
    for number, title in doc['milestones'].items():
        members = [n for n in names if str(doc['programs'][n]['milestone']) == number]
        label = f'{number:>2} {title}'
        if number == '2':
            # Milestone 2 is the whole design corpus parsing through checking.
            checked = sum(r.checked for r in design.values())
            print(f'  {label:<40} {f"{checked}/{len(names)}":>8} {"":>8}  (design files that check)')
            continue
        if not members:
            print(f'  {label:<40} {"-":>8} {"-":>8}')
            continue
        passed = sum(design[n].ok for n in members)
        working = sum(core[n].ok for n in members)
        print(f'  {label:<40} {f"{passed}/{len(members)}":>8} {f"{working}/{len(members)}":>8}')
    total_design = sum(r.ok for r in design.values())
    total_core = sum(r.ok for r in core.values())
    print(f'  {"   total":<40} {f"{total_design}/{len(names)}":>8} {f"{total_core}/{len(names)}":>8}')
    failing = [n for n in names if not design[n].ok]
    if failing:
        print('Design failures (first error):')
        width = max(len(n) for n in failing)
        for name in failing:
            print(f'  {name:<{width}}  {design[name].error}')


def arguments(argv: list[str] | None = None):
    cli = argparse.ArgumentParser(prog='python3 -m tools.core ladder', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('-k', dest='keyword', default='', metavar='WORDS', help='select programs by name')
    cli.add_argument('-n', dest='workers', type=int, default=None, help='parallel workers (default: up to 4)')
    cli.add_argument('--update-ratchet', action='store_true',
                     help='add newly passing design programs to design_passing')
    cli.add_argument('--json', type=Path, dest='json_output', metavar='PATH',
                     help='write fresh target-scoped results as JSON (build output only)')
    cli.add_argument('--compiler', type=Path, help='use this compiler instead of the cached build')
    return cli.parse_args(argv)


def main(argv: list[str] | None = None, compiler: Path | None = None) -> int:
    options = arguments(argv)
    compiler = options.compiler or compiler
    if compiler is None:
        print('ladder: pass --compiler or run through python3 -m tools.core ladder', file=sys.stderr)
        return 2
    workers = options.workers if options.workers is not None else default_workers()
    return run(Path(compiler).resolve(), keyword=options.keyword, workers=workers or 1,
               update_ratchet=options.update_ratchet, json_output=options.json_output)


if __name__ == '__main__':
    raise SystemExit(main())
