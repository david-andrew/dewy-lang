"""Score the acceptance ladder in tests/ladder (see ROADMAP.md).

    python3 -m tools.core ladder [-k WORDS] [-n N] [--update-ratchet]

Each program has `design.dewy` (the design surface), usually `core.dewy`
(today's accepted dialect) and `expected.out` from the independent oracles. A
version passes when it checks, builds (native, release), exits 0 and prints
exactly the expected output; `stdin.txt`, when present, is its input. A
program whose ladder.json entry has `expect.kind = "compile-error"` must be
rejected instead: its design passes only when `check` fails with a semantic
diagnostic matching `expect.diagnostic` (at `expect.line`, when given).
Unsupported-feature and parse errors are not rejections, and acceptance is
reported as "wrongly accepted". A program with `expect.kind = "tests"` also
runs its `$test` functions (`dewy-core test --json`): its design passes only
when the per-test results, counts, exit status, a failed test's output and
message match `expected-tests.json`, as well as main's output. Programs marked `open` depend on an open design
question: they run and are listed, but never count toward the design totals or
the ratchet. The command fails when a core version fails or a design program
listed in ladder.json's "design_passing" ratchet stops passing.
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

DIAGNOSTIC = re.compile(r'^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+): error: (?P<message>.*)$')
# A rejection must come from checking the program, not from a missing feature...
UNSUPPORTED = re.compile(r'is part of the design but not implemented yet|does not yet support|unknown directive')
# ...or from the lexer/parser (their messages, from compiler/dewy_fast.jo).
PARSE = re.compile(
    r"^(expected (an expression|a declaration|a block element|a body after|a member name|a name after \$"
    r"|one interpolation expression|digits after|exponent digits|hexadecimal digits|1–6 hex digits|'|`\$field)"
    r"|unexpected character|unterminated |incomplete string escape|unsupported string escape|unicode escape"
    r"|.*\bis nested too deeply|invalid (numeric|based-string) digit|based-string padding)", re.IGNORECASE)


@dataclass
class Result:
    program: str
    version: str
    ok: bool
    checked: bool
    error: str = ''
    # Programs that must be rejected also record how: rejected, wrongly-accepted,
    # unsupported, parse-error or other-error.
    status: str = ''


def first_error(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    line = next((line for line in lines if 'error' in line.lower()), lines[0] if lines else '(no output)')
    return line.replace(str(LADDER) + os.sep, '')


def rejects(entry: dict) -> bool:
    return entry.get('expect', {}).get('kind') == 'compile-error'


def scores_tests(entry: dict | None) -> bool:
    return entry is not None and entry.get('expect', {}).get('kind') == 'tests'


def has_core(name: str) -> bool:
    return (LADDER / name / 'core.dewy').exists()


def evaluate(compiler: Path, directory: Path, version: str, scratch: Path, env: dict,
             entry: dict | None = None) -> Result:
    source = directory / f'{version}.dewy'
    work = Path(tempfile.mkdtemp(prefix=f'{directory.name}-{version}-', dir=scratch))

    def step(command, timeout=120, stdin: Path | None = None):
        try:
            if stdin is not None:
                return subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, errors='replace',
                                      timeout=timeout, check=False, input=stdin.read_text())
            return subprocess.run(command, cwd=work, env=env, capture_output=True, text=True, errors='replace',
                                  timeout=timeout, check=False, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(command, 'timeout', '', f'timed out after {timeout} s')

    checked = step([str(compiler), 'check', str(source)])
    if version == 'design' and entry is not None and rejects(entry):
        return rejection(directory.name, source, checked, entry['expect'])
    if checked.returncode != 0:
        return Result(directory.name, version, False, False, first_error(checked.stderr + checked.stdout))
    binary = work / 'program'
    built = step([str(compiler), 'build', str(source), '--release', '-o', str(binary)])
    if built.returncode != 0:
        return Result(directory.name, version, False, True, first_error(built.stderr + built.stdout))
    if not binary.exists() and binary.with_suffix('.exe').exists():
        binary = binary.with_suffix('.exe')
    stdin = directory / 'stdin.txt'
    ran = step([str(binary)], RUN_TIMEOUT, stdin if stdin.exists() else None)
    expected = (directory / 'expected.out').read_text()
    if ran.returncode != 0:
        detail = first_error(ran.stderr + ran.stdout) if (ran.stderr + ran.stdout).strip() else ''
        return Result(directory.name, version, False, True, f'exit {ran.returncode} {detail}'.strip())
    if ran.stdout != expected:
        return Result(directory.name, version, False, True,
                      f'printed {ran.stdout.strip()[:120]!r}, expected {expected.strip()[:120]!r}')
    if version == 'design' and scores_tests(entry):
        tested = step([str(compiler), 'test', '--release', '--json', str(source)], RUN_TIMEOUT)
        problem = test_mismatch(tested, json.loads((directory / 'expected-tests.json').read_text()), ran.stdout)
        if problem:
            return Result(directory.name, version, False, True, problem)
    return Result(directory.name, version, True, True)


def test_mismatch(tested: subprocess.CompletedProcess, want: dict, ordinary: str) -> str:
    """How `dewy-core test --json` results differ from expected-tests.json ('' when they agree)."""
    tests, summary = {}, None
    for line in tested.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            return f'test output is not JSON: {line[:120]!r} {first_error(tested.stderr)}'.strip()
        if 'test' in item:
            tests[item['test']] = item
        else:
            summary = item
    if summary is None:
        return f'tests did not finish (exit {tested.returncode}): {first_error(tested.stderr + tested.stdout)}'
    statuses = {name: item['status'] for name, item in tests.items()}
    if list(statuses.items()) != list(want['cases'].items()):
        return f'test results {statuses}, expected {want["cases"]}'
    for key in ('passed', 'failed'):
        if summary.get(key) != want[key]:
            return f'{summary.get(key)} {key}, expected {want[key]}'
    if tested.returncode != want['exit']:
        return f'tests exited {tested.returncode}, expected {want["exit"]}'
    failed = [item for item in tests.values() if item['status'] != 'pass']
    if 'failure_stdout' in want and any(item.get('stdout') != want['failure_stdout'] for item in failed):
        return f'a failed test printed {[item.get("stdout") for item in failed]}, expected {want["failure_stdout"]!r}'
    if 'message_contains' in want and any(want['message_contains'] not in item.get('output', '') for item in failed):
        return f'a failed test does not report {want["message_contains"]!r}'
    if 'ordinary_stdout' in want and ordinary != want['ordinary_stdout']:
        return f'main printed {ordinary!r}, expected {want["ordinary_stdout"]!r}'
    return ''


def rejection(name: str, source: Path, checked: subprocess.CompletedProcess, expect: dict) -> Result:
    """Score a program that must be rejected: a matching semantic diagnostic, and nothing unsupported."""
    output = checked.stderr + checked.stdout
    if checked.returncode == 0:
        return Result(name, 'design', False, True, 'wrongly accepted: check succeeded', 'wrongly-accepted')
    first = first_error(output)
    if UNSUPPORTED.search(output):
        return Result(name, 'design', False, False, f'unsupported, not a rejection: {first}', 'unsupported')
    errors = [match for match in map(DIAGNOSTIC.match, output.splitlines()) if match]
    if any(PARSE.match(match['message']) for match in errors):
        return Result(name, 'design', False, False, f'parse error, not a rejection: {first}', 'parse-error')
    pattern = re.compile(expect['diagnostic'], re.IGNORECASE)
    line = expect.get('line')
    for match in errors:
        if pattern.search(match['message']) and (line is None or (int(match['line']) == line
                                                                   and Path(match['path']).name == source.name)):
            return Result(name, 'design', True, True, status='rejected')
    where = f' at line {line}' if line is not None else ''
    return Result(name, 'design', False, True, f'expected /{expect["diagnostic"]}/{where}, got {first}',
                  'other-error')


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
    # The layout ladder.json is kept in, so ratchet updates stay small diffs.
    (LADDER / 'ladder.json').write_text(json.dumps(doc, indent=1) + '\n')


def tiers(doc: dict) -> list[tuple[str, list[str]]]:
    """(label, milestone numbers) for each tier; ladder.json gives milestone ranges per tier."""
    ranges = doc.get('tiers') or {'': [1, len(doc['milestones'])]}
    return [(label, [m for m in doc['milestones'] if low <= int(m) <= high]) for label, (low, high) in ranges.items()]


def validate(doc: dict) -> list[str]:
    problems = []
    directories = sorted(p.name for p in LADDER.iterdir() if p.is_dir() and p.name[:2].isdigit())
    if sorted(doc['programs']) != directories:
        problems.append('ladder.json programs and tests/ladder directories differ')
    for name, entry in doc['programs'].items():
        if not (LADDER / name).is_dir():
            continue
        negative = rejects(entry)
        if not (LADDER / name / 'design.dewy').exists():
            problems.append(f'{name} lacks design.dewy')
        if (not negative or has_core(name)) and not (LADDER / name / 'expected.out').exists():
            problems.append(f'{name} lacks expected.out')
        if str(entry.get('milestone')) not in doc['milestones']:
            problems.append(f'{name} needs a milestone from 1 to {len(doc["milestones"])}')
        if negative:
            try:
                re.compile(entry['expect']['diagnostic'])
            except (KeyError, re.error):
                problems.append(f'{name} needs expect.diagnostic, a regular expression')
        elif scores_tests(entry):
            if not (LADDER / name / 'expected-tests.json').exists():
                problems.append(f'{name} lacks expected-tests.json')
        elif entry.get('expect', {}).get('kind', 'stdout') != 'stdout':
            problems.append(f'{name} has an unknown expect.kind')
        if entry.get('open') and name in doc['design_passing']:
            problems.append(f'{name} is open and cannot be in design_passing')
    for name in doc['design_passing']:
        if name not in doc['programs']:
            problems.append(f'design_passing lists unknown program {name}')
    tiered = [m for _, members in tiers(doc) for m in members]
    if sorted(tiered) != sorted(doc['milestones']):
        problems.append('every milestone needs exactly one tier')
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
    programs = doc['programs']
    names = [name for name in programs if selected(name)]
    if not names:
        print('ladder: no programs selected', file=sys.stderr)
        return 0
    scratch = Path(tempfile.mkdtemp(prefix='dewy-ladder-'))
    env = clean_environment()
    env['SLOPPY_THREADS'] = '2'
    jobs = [(name, version) for name in names for version in ('design', 'core')
            if version == 'design' or has_core(name)]
    parallel = [job for job in jobs if not programs[job[0]].get('serial')]
    serial = [job for job in jobs if programs[job[0]].get('serial')]
    results: dict[tuple[str, str], Result] = {}

    def job(name, version):
        return evaluate(compiler, LADDER / name, version, scratch, env, programs[name])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(job, n, v): (n, v) for n, v in parallel}
        for future in concurrent.futures.as_completed(futures):
            results[futures[future]] = future.result()
    if serial:
        with port_lock():
            for name, version in serial:
                results[name, version] = job(name, version)
    shutil.rmtree(scratch, ignore_errors=True)

    design = {n: results[n, 'design'] for n in names}
    core = {n: results[n, 'core'] for n in names if (n, 'core') in results}
    scored = [n for n in names if not programs[n].get('open')]
    ratchet = set(doc['design_passing'])
    regressed = sorted(n for n in names if n in ratchet and not design[n].ok)
    core_failed = sorted(n for n in core if not core[n].ok)
    newly = sorted(n for n in scored if design[n].ok and n not in ratchet)
    elapsed = time.perf_counter() - started

    if json_output is not None:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        payload = {
            'schema': 2, 'revision': revision,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
            'host': f'{sys.platform}-{platform.machine()}', 'target': 'native-release',
            'milestones': doc['milestones'],
            'results': [dict(asdict(results[n, v]), milestone=programs[n]['milestone'],
                             open=bool(programs[n].get('open')),
                             expect=programs[n].get('expect', {}).get('kind', 'stdout'))
                        for n, v in jobs],
        }
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2) + '\n')

    if scoreboard:
        print_scoreboard(doc, names, design, core)
    else:
        opened = len(names) - len(scored)
        print(f'ladder: design {sum(design[n].ok for n in scored)}/{len(scored)}'
              + (f' (+{opened} open)' if opened else '')
              + f', core {sum(r.ok for r in core.values())}/{len(core)} in {elapsed:.1f} s', flush=True)
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
    programs = doc['programs']
    is_open = lambda n: bool(programs[n].get('open'))
    width = max(len(f'{n:>2} {t}') for n, t in doc['milestones'].items())

    def row(label, members, note=''):
        scored = [n for n in members if not is_open(n)]
        cores = [n for n in members if n in core]
        passed = f'{sum(design[n].ok for n in scored)}/{len(scored)}' if scored else '-'
        working = f'{sum(core[n].ok for n in cores)}/{len(cores)}' if cores else '-'
        opened = len(members) - len(scored)
        extra = '  '.join(part for part in (f'{opened} open' if opened else '', note) if part)
        print(f'  {label:<{width}} {passed:>8} {working:>8}' + (f'  {extra}' if extra else ''))

    print('Acceptance ladder (native release builds; open programs are excluded from design counts)')
    for label, milestones in tiers(doc):
        group = [n for n in names if str(programs[n]['milestone']) in milestones]
        if not group:
            continue
        numbers = sorted(int(n[:2]) for n in group)
        heading = f'Tier {label} (programs {numbers[0]:02}–{numbers[-1]:02})' if label else 'Programs'
        print(f'{heading:<{width + 2}} {"design":>8} {"core":>8}')
        for number in milestones:
            title = doc['milestones'][number]
            members = [n for n in group if str(programs[n]['milestone']) == number]
            label_text = f'{number:>2} {title}'
            if number == '2':
                # Milestone 2 is the whole tier's design corpus parsing through checking.
                checked = sum(design[n].checked for n in group)
                print(f'  {label_text:<{width}} {f"{checked}/{len(group)}":>8} {"":>8}  (design files that check)')
                continue
            row(label_text, members)
        row(f'   tier {label}' if label else '   total', group)
    if len(tiers(doc)) > 1:
        scored = [n for n in names if not is_open(n)]
        opened = len(names) - len(scored)
        print(f'Design total: {sum(design[n].ok for n in scored)}/{len(scored)}'
              + (f', excluding {opened} open' if opened else ''))

    failing = [n for n in names if not design[n].ok and not is_open(n) and design[n].status != 'wrongly-accepted']
    accepted = [n for n in names if design[n].status == 'wrongly-accepted']
    opened = [n for n in names if is_open(n)]
    pad = max(map(len, failing + accepted + opened), default=0)
    if failing:
        print('Design failures (first error):')
        for name in failing:
            print(f'  {name:<{pad}}  {design[name].error}')
    if accepted:
        print('Wrongly accepted (must be rejected):')
        for name in accepted:
            print(f'  {name:<{pad}}' + ('  (open)' if is_open(name) else ''))
    if opened:
        print('Open (excluded from design counts; the program does not yet settle its question):')
        for name in opened:
            result = design[name]
            state = 'runs' if result.ok else result.error
            print(f'  {name:<{pad}}  {state}')
            print(f'  {"":<{pad}}  open: {programs[name]["open"]}')


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
