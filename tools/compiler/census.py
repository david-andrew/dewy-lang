"""Run `check --obligations` on a frozen, newline-delimited list of programs.

    python3 -m tools.compiler.census PROGRAMS --compiler COMPILER --out REPORT.jsonl

The manifest uses checkout-relative paths. Keep the same manifest to compare
revisions. The raw report keeps rejected inputs separate from completed checks.
"""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from tools import headless
from tools.compiler.bench import BENCH, ROOT, prepare_source

OBLIGATION = re.compile(
    r'(.+?):(\d+):(\d+): (.*?) \((?:\$runtime_checks|\$prototype|library|Sloppy source)\)'
)
EXIT_CALL = re.compile(r'\bexit\s*\(')


def kind(message: str, test_exit: bool = False) -> str:
    """Classify the obligation itself, independent of its diagnostic repair text."""
    if message.startswith('may panic:'):
        return 'callee panic'
    if 'array shape/index contract' in message:
        return 'array shape/index contract'
    if 'fixed-size array conversion' in message:
        return 'fixed-size array conversion'
    if 'exact integer result fits' in message or 'the exact sum' in message:
        return 'fixed-width arithmetic'
    if 'for the conversion to ' in message:
        if 'is a number within' in message:
            return 'float-to-integer conversion'
        return 'test exit narrowing' if test_exit else 'integer fit conversion'
    if message.startswith('runtime check: refinement'):
        return 'refinement'
    if 'key is in the dictionary' in message:
        return 'dictionary membership'
    if 'handle is in the pool' in message:
        return 'pool membership'
    if 'value is in the set' in message:
        return 'set membership'
    if 'reshape' in message or 'elementwise' in message or 'assigned' in message and 'slice' in message:
        return 'shape relation'
    if 'slice' in message or "find's start" in message:
        return 'slice/char bounds'
    if any(text in message for text in ('index is in bounds', 'index is not in bounds',
                                        'element read is in bounds', "loop's read", 'read<uint')):
        return 'index bounds'
    if any(text in message for text in ('divisor', 'exponent', 'range step', 'shift count')):
        return 'division/domain'
    if any(text in message for text in ('length (unpacking', 'length (spreading',
                                        'nonempty', 'pop() has an element', "truncate's count")):
        return 'length/nonempty'
    if 'open range' in message:
        return 'range exhaustion'
    if 'NaN' in message or '$no_inf' in message:
        return 'float contract'
    if 'drawing runs only' in message:
        return 'drawing context'
    return 'unclassified'


def scan(compiler: Path, program: str, source: Path) -> dict:
    if not source.is_file():
        return dict(path=program, rc=1, stdout='', stderr='program is missing')
    try:
        result = subprocess.run([compiler, 'check', '--obligations', source.name], cwd=source.parent,
                                capture_output=True, text=True, errors='replace', timeout=90)
    except subprocess.TimeoutExpired:
        return dict(path=program, rc=1, stdout='', stderr='check timed out')
    # Prepared bench copies keep their checked-in names and line numbers.
    stdout = result.stdout
    if source.parent != (ROOT / program).parent:
        stdout = stdout.replace(f'{source.parent}{os.sep}', '')
    return dict(path=program, rc=result.returncode, stdout=stdout, stderr=result.stderr)


def sites(records, root: Path = ROOT):
    """Deduplicate on source location and obligation text, including shared imports."""
    found = defaultdict(set)
    for record in records:
        if record['rc']:
            continue
        program = Path(record['path'])
        for line in record['stdout'].splitlines():
            match = OBLIGATION.fullmatch(line)
            if match is None:
                continue
            filename, row, column, message = match.groups()
            path = (root / program.parent / filename).resolve()
            if path.is_relative_to(root):
                path = path.relative_to(root)
            found[path, int(row), int(column), message].add(program)
    return found


def counts(found, root: Path = ROOT) -> Counter:
    @lru_cache(maxsize=None)
    def source_lines(path: Path) -> list[str]:
        source = root / path
        return source.read_text(errors='replace').splitlines() if source.is_file() else []

    output = Counter()
    for path, row, column, message in found:
        test_exit = False
        if path.parts[:2] == ('tests', 'cases') and 'for the conversion to uint8' in message:
            lines = source_lines(path)
            if 0 < row <= len(lines):
                prefix = lines[row - 1].encode()[:column - 1].decode(errors='ignore')
                for call in EXIT_CALL.finditer(prefix):
                    argument = prefix[call.end():]
                    if argument.count('(') >= argument.count(')'):
                        test_exit = True
                        break
        output[kind(message, test_exit)] += 1
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('programs', type=Path)
    parser.add_argument('--compiler', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='raw JSONL report and scratch parent')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    headless.activate()
    os.environ['DEWY_CORE_LIB'] = str(ROOT / 'lib')
    compiler = args.compiler.resolve(strict=True)
    programs = list(dict.fromkeys(line for line in args.programs.read_text().splitlines() if line))
    with tempfile.TemporaryDirectory(prefix='bench-', dir=args.out.parent.resolve()) as temporary:
        work = Path(temporary)
        inputs = []
        for program in programs:
            source = ROOT / program
            if source.parent == BENCH and source.is_file() and 'p"harness.dewy"' in source.read_text():
                source = prepare_source(source.stem, work)
            inputs.append(source)
        with ThreadPoolExecutor(args.workers) as pool:
            records = list(pool.map(lambda pair: scan(compiler, *pair), zip(programs, inputs)))
    with args.out.open('w') as stream:
        for record in records:
            stream.write(json.dumps(record) + '\n')
    found = sites(records)
    affected = set().union(*found.values())
    rejected = sum(record['rc'] != 0 for record in records)
    print(f'{len(found)} sites in {len(affected)} of {len(records)} programs, {rejected} checks failed')
    for label, count in counts(found).most_common():
        print(f'{count:5} {label}')


if __name__ == '__main__':
    main()
