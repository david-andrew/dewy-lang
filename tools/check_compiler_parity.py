"""Compare hosted and native acceptance and execution, one fixture at a time.

Use the existing end-to-end fixture expectations by default, or supply a JSON
list of {source, accepts, exit, args, stdout} cases. Rejections need only source
and accepts=false. Compiler errors, timeouts and runtime failures are recorded
separately. A failed fixture never prevents later fixtures from being checked.
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
                and ('stdout' not in case or run.get('stdout') == case['stdout']))
    # A timeout, signal, traceback, or backend failure is not a successful
    # language-level rejection. Keep this distinct from a program exiting 1.
    return (compiled['status'] == 1 and 'Error:' in compiled['stderr']
            and 'Traceback' not in compiled['stderr']
            and not list(work.rglob('*.udewy')))


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
                'target': args.target, 'cases': cases}
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
            record['same_output'] = all(left[key] == right[key] for key in ('stdout_hex', 'stderr_hex'))
        record['passed'] = all(outcomes) and record.get('same_output', True)
        passed += record['passed']
        with (output / 'results.jsonl').open('a') as results:
            results.write(json.dumps(record) + '\n')
        print(f'{index + 1}/{len(cases)} {source.name}: {"PASS" if record["passed"] else "FAIL"}', flush=True)
    print(f'{passed}/{len(cases)} parity cases passed', flush=True)
    return int(passed != len(cases))


if __name__ == '__main__':
    raise SystemExit(main())
