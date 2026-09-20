"""Aggregate the copies `dewy analyze` reports for a program.

Usage: python tools/copy_report.py [--compiler CMD] [--by kind|site|reason|file] FILE.dewy

Runs `CMD analyze FILE` (default: the hosted compiler, `python -m dewy`) and
counts the `copy:` lines it prints, grouped by kind, site or reason. The
native compiler prints the same lines, so `--compiler path/to/dewy` compares
the two. This is the copy budget of Phase 1.1: the total and its breakdown
on the compiler's own sources (`dewy/bootstrap/main.dewy`) are recorded in
`dewy/bootstrap/PHASE0_MEASUREMENTS.md`.
"""

from __future__ import annotations

import re
import json
import shlex
import subprocess
import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

LINE = re.compile(r'^copy: (?P<file>.*?):(?P<row>\d+): (?P<kind>\w+) (?:`(?P<type>.*?)` )?copied when (?P<site>.*?): (?P<reason>.*)$')


def main(argv: list[str]) -> int:
    parser = ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('file')
    parser.add_argument('--compiler', default=None, help='compiler command (default: python -m dewy)')
    parser.add_argument('--by', choices=['kind', 'site', 'reason', 'type', 'file'], default='reason')
    parser.add_argument('--only', default=None, help='keep copies whose file path contains this text')
    parser.add_argument('--top', type=int, default=25)
    parser.add_argument('--max-copies', type=int, help='fail if the filtered static copy-site count exceeds this budget')
    parser.add_argument('--json', action='store_true', help='emit a versioned inventory for stored baselines')
    args = parser.parse_args(argv)
    if args.max_copies is not None and args.max_copies < 0:
        parser.error('--max-copies must be nonnegative')
    command = shlex.split(args.compiler) if args.compiler else [sys.executable, '-m', 'dewy']
    result = subprocess.run([*command, 'analyze', args.file], capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    # A failed analysis may already have printed some copy notes. It is not
    # a complete inventory and must never pass a copy-budget gate.
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        return result.returncode
    lines = result.stdout.splitlines()
    copy_lines = [line for line in lines if line.startswith('copy: ')]
    parsed = [LINE.fullmatch(line) for line in copy_lines]
    summaries = [line for line in lines if line.startswith('copy report: ')]
    if any(match is None for match in parsed) or len(summaries) != 1:
        sys.stderr.write('copy inventory is incomplete: malformed entries or missing/duplicate summary\n')
        return 1
    notes = [match.groupdict() for match in parsed]
    reported = dict((kind, int(count)) for count, kind in re.findall(r'(\d+) (record|array|cell|string)\b', summaries[0]))
    actual = Counter(note['kind'] for note in notes)
    if set(reported) != {'record', 'array', 'cell', 'string'} or any(actual[kind] != count for kind, count in reported.items()) or set(actual) - set(reported):
        sys.stderr.write('copy inventory is incomplete: entries disagree with the compiler summary\n')
        return 1
    if args.only:
        notes = [note for note in notes if args.only in note['file']]
    kinds = Counter(note['kind'] for note in notes)
    over_budget = args.max_copies is not None and len(notes) > args.max_copies
    if args.json:
        print(json.dumps(dict(version=1, source=args.file, compiler=command, only=args.only,
                              count=len(notes), kinds=dict(kinds), notes=notes,
                              budget=args.max_copies, within_budget=not over_budget), indent=2))
    else:
        print(f"{len(notes)} copies: " + ', '.join(f'{kinds[k]} {k}' for k in ('record', 'array', 'cell', 'string') if kinds[k]))
    groups = Counter()
    for note in notes:
        key = note[args.by] or ''
        # collapse the binding names in reasons so equal causes group together
        if args.by == 'reason':
            key = re.sub(r'`[^`]*`', '`_`', key)
        groups[key] += 1
    if not args.json:
        for key, count in groups.most_common(args.top):
            print(f'{count:7d}  {key}')
    if over_budget:
        sys.stderr.write(f'copy budget exceeded: {len(notes)} sites > {args.max_copies} allowed\n')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
