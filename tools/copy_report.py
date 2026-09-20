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
    args = parser.parse_args(argv)
    command = args.compiler.split() if args.compiler else [sys.executable, '-m', 'dewy']
    result = subprocess.run([*command, 'analyze', args.file], capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    notes = [m.groupdict() for m in map(LINE.match, result.stdout.splitlines()) if m]
    if args.only:
        notes = [note for note in notes if args.only in note['file']]
    if not notes and result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    kinds = Counter(note['kind'] for note in notes)
    print(f"{len(notes)} copies: " + ', '.join(f'{kinds[k]} {k}' for k in ('record', 'array', 'cell', 'string') if kinds[k]))
    groups = Counter()
    for note in notes:
        key = note[args.by] or ''
        # collapse the binding names in reasons so equal causes group together
        if args.by == 'reason':
            key = re.sub(r'`[^`]*`', '`_`', key)
        groups[key] += 1
    for key, count in groups.most_common(args.top):
        print(f'{count:7d}  {key}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
