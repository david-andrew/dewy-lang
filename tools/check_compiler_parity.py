"""Compare hosted and native acceptance and execution, one fixture at a time.

Use the existing end-to-end fixture expectations by default, or supply a JSON
list of {source, accepts, exit, args, stdout} cases. An expected runtime report
can specify diagnostic_stderr as a nonempty list of required report fragments;
only those cases permit diagnostic formatting/notes to differ. Rejections need
only source and accepts=false. Compiler errors, timeouts and runtime failures
are recorded separately. A failed fixture never prevents later fixtures from
being checked.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from udewy.cache import cache_artifact


def fixture_cases() -> list[dict]:
    module = ast.parse((ROOT / 'tests/python_misc/test_cleanparse_udewy_e2e.py').read_text())
    assignment = next(node for node in module.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'LOWERED_CASES' for target in node.targets))
    accepted = [{'source': f'dewy/tests/{name}', 'accepts': True, 'exit': status}
                for name, status in ast.literal_eval(assignment.value)]
    expectations = json.loads((ROOT / 'tests/fixtures/compiler_parity_expectations.json').read_text())
    for case in accepted:
        case.update(expectations.pop(case['source'], {}))
    if expectations:
        raise ValueError(f'parity expectations reference absent fixtures: {list(expectations)}')
    rejected = json.loads((ROOT / 'tests/fixtures/compiler_parity_rejections.json').read_text())
    return [*accepted, *rejected]


def invoke(command: list[str], work: Path, env: dict, timeout: float) -> dict:
    started = time.perf_counter()
    process = subprocess.Popen(command, cwd=work, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        status = process.returncode
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        status = 'timeout'
    return {'status': status, 'seconds': time.perf_counter() - started,
            'stdout': stdout.decode(errors='replace'), 'stderr': stderr.decode(errors='replace'),
            'stdout_hex': stdout.hex(), 'stderr_hex': stderr.hex()}


def expected_outcome(case: dict, result: dict, work: Path) -> bool:
    compiled = result['compile']
    if case['accepts']:
        run = result.get('run', {})
        return (compiled['status'] == 0 and run.get('status') == case['exit']
                and ('stdout' not in case or run.get('stdout') == case['stdout'])
                and ('diagnostic_stderr' not in case or
                     bool(case['diagnostic_stderr']) and all(
                         fragment in run.get('stderr', '') for fragment in case['diagnostic_stderr'])))
    # A timeout, signal, traceback, or backend failure is not a successful
    # language-level rejection. Keep this distinct from a program exiting 1.
    return (compiled['status'] == 1 and 'Error:' in compiled['stderr']
            and 'Traceback' not in compiled['stderr']
            and not list(work.rglob('*.udewy')))


def same_output(case: dict, left: dict, right: dict, left_work: 'Path | None' = None, right_work: 'Path | None' = None) -> bool:
    # Ordinary stderr is program output and remains byte-exact. For an
    # explicitly specified failure report, each implementation has already
    # passed its expected fragments, exit and stdout checks independently.
    # A program printing its own path (`argv[0]`) differs only by the
    # per-implementation work directory, which is not program behavior.
    streams = ('stdout_hex',) if case.get('diagnostic_stderr') else ('stdout_hex', 'stderr_hex')

    def normalized(result: dict, key: str, work: 'Path | None') -> bytes:
        data = bytes.fromhex(result[key])
        return data.replace(str(work).encode(), b'<work>') if work is not None else data

    return all(normalized(left, key, left_work) == normalized(right, key, right_work) for key in streams)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-executable', type=Path, required=True)
    parser.add_argument('--udewy-executable', type=Path, required=True)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--hosted-root', type=Path, default=ROOT,
                        help='hosted package/library snapshot; fixtures remain in this checkout')
    parser.add_argument('--match', default='*', help='fixture filename glob')
    parser.add_argument('--target', choices=('x86_64', 'c'), default='x86_64')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--shared-prelude-cache', action='store_true',
                        help='share checked preludes across cases; keep all other artifacts isolated')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    cases = json.loads(args.cases.read_text()) if args.cases else fixture_cases()
    cases = [case for case in cases if fnmatch.fnmatch(Path(case['source']).name, args.match)]
    if not cases:
        parser.error('no matching cases')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'results.jsonl').exists():
        parser.error('use a fresh output directory to preserve the previous inventory')
    native = args.native_executable.resolve(strict=True)
    micro = args.udewy_executable.resolve(strict=True)
    hosted_root = args.hosted_root.resolve(strict=True)
    metadata = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'hosted_root': str(hosted_root),
                'hosted_source_sha256': hashlib.sha256(b''.join(
                    str(path.relative_to(hosted_root)).encode() + b'\0' + path.read_bytes()
                    for package in ('dewy', 'udewy', 'library')
                    for path in sorted((hosted_root / package).rglob('*'))
                    if path.is_file() and path.suffix in ('.py', '.dewy', '.udewy'))).hexdigest(),
                'native': str(native), 'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
                'udewy': str(micro), 'udewy_sha256': hashlib.sha256(micro.read_bytes()).hexdigest(),
                'target': args.target, 'cases': cases,
                'shared_prelude_cache': args.shared_prelude_cache,
                'analysis_environment': {name: os.environ[name] for name in
                    ('DEWY_NO_PRELUDE_CACHE', 'DEWY_NO_RESIDENT_PRELUDE') if name in os.environ}}
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    env = os.environ | {'PYTHONPATH': str(ROOT), 'DEWY_LIBRARY_ROOT': str(ROOT / 'library'), 'DEWY_UDEWY': str(micro)}
    passed = 0
    for index, case in enumerate(cases):
        source = (ROOT / case['source']).resolve(strict=True)
        record = {'source': str(source), 'expected': case}
        outcomes = []
        for label, compiler in [('hosted', [sys.executable, '-m', 'dewy']), ('native', [str(native)])]:
            work = output / f'{index:03}-{source.stem}' / label
            work.mkdir(parents=True)
            if args.shared_prelude_cache:
                # Only checked preludes cross case boundaries. Each compiler
                # retains its own cache format, and emitted programs remain
                # local so an earlier executable cannot satisfy a later case.
                shared = output / 'prelude-cache' / label
                shared.mkdir(parents=True, exist_ok=True)
                cache = work / '__dewycache__'
                cache.mkdir()
                (cache / 'prelude').symlink_to(shared, target_is_directory=True)
            compiler_env = env | {'PYTHONPATH': str(hosted_root), 'DEWY_LIBRARY_ROOT': str(hosted_root / 'library')} if label == 'hosted' else env
            compiled = invoke([*compiler, '--target', args.target, '-c', str(source)], work, compiler_env, args.timeout)
            result = {'compile': compiled}
            if case['accepts']:
                binary = work / cache_artifact(source, cwd=work)
                if compiled['status'] == 0 and binary.is_file():
                    result['run'] = invoke([str(binary), *case.get('args', [])], work, env, args.timeout)
            result['passed'] = expected_outcome(case, result, work)
            record[label] = result
            outcomes.append(result['passed'])
            (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        if all(outcomes) and case['accepts']:
            left, right = record['hosted']['run'], record['native']['run']
            record['same_output'] = same_output(case, left, right, output / f'{index:03}-{source.stem}' / 'hosted', output / f'{index:03}-{source.stem}' / 'native')
            record['same_stderr_bytes'] = left['stderr_hex'] == right['stderr_hex']
        record['passed'] = all(outcomes) and record.get('same_output', True)
        passed += record['passed']
        with (output / 'results.jsonl').open('a') as results:
            results.write(json.dumps(record) + '\n')
        print(f'{index + 1}/{len(cases)} {source.name}: {"PASS" if record["passed"] else "FAIL"}', flush=True)
    print(f'{passed}/{len(cases)} parity cases passed', flush=True)
    return int(passed != len(cases))


if __name__ == '__main__':
    raise SystemExit(main())
