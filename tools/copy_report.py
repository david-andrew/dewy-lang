"""Aggregate the copies `dewy analyze` reports for a program.

Usage: python tools/copy_report.py [--compiler CMD] [--by kind|site|reason|file] FILE.dewy

Runs `CMD analyze FILE` (default: the hosted compiler, `python -m dewy`) and
counts the `copy:` lines it prints, grouped by kind, site or reason. The
native compiler prints the same lines, so `--compiler path/to/dewy` compares
the two. This is the copy budget of Phase 1.1: the total and its breakdown
on the compiler's own sources (`dewy/bootstrap/main.dewy`) are recorded in
`dewy/bootstrap/PHASE0_MEASUREMENTS.md`.

Use --scope FILE_OR_DIRECTORY --max-copies N for a kernel gate, or add
--max-copies-per-kloc N for a density gate. Density counts physical lines in
all selected .dewy files, including files with zero copy sites. It measures
static sites, not execution frequency, allocated bytes, or elapsed time.
"""

from __future__ import annotations

import re
import math
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
    parser.add_argument('--scope', type=Path, help='restrict the inventory to a source file or directory (also defines the line-count denominator)')
    parser.add_argument('--max-copies-per-kloc', type=float, help='maximum static sites per 1000 physical Dewy source lines; requires --scope')
    parser.add_argument('--json', action='store_true', help='emit a versioned inventory for stored baselines')
    args = parser.parse_args(argv)
    if args.max_copies is not None and args.max_copies < 0:
        parser.error('--max-copies must be nonnegative')
    if args.max_copies_per_kloc is not None:
        if not math.isfinite(args.max_copies_per_kloc) or args.max_copies_per_kloc < 0:
            parser.error('--max-copies-per-kloc must be finite and nonnegative')
        if args.scope is None:
            parser.error('--max-copies-per-kloc requires --scope')
    root = Path(__file__).resolve().parent.parent
    scope_files = None
    source_lines = None
    if args.scope is not None:
        scope = args.scope.resolve()
        candidates = [scope] if scope.is_file() else scope.rglob('*.dewy') if scope.is_dir() else []
        scope_files = {path.resolve() for path in candidates if path.is_file() and path.suffix == '.dewy'
                       and '__dewycache__' not in path.parts and (args.only is None or args.only in str(path))}
        if not scope_files:
            parser.error('--scope must select at least one .dewy source file')
        try:
            source_lines = sum(len(path.read_text().splitlines()) for path in scope_files)
        except (OSError, UnicodeError) as error:
            parser.error(f'cannot count source lines: {error}')
        if source_lines == 0:
            parser.error('--scope has no source lines')
    command = shlex.split(args.compiler) if args.compiler else [sys.executable, '-m', 'dewy']
    result = subprocess.run([*command, 'analyze', args.file], capture_output=True, text=True, cwd=root)
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
    # Hosted reports also describe moves; native reports end after
    # strings. Accept both complete formats, without allowing repeated kinds.
    summary = re.fullmatch(r'copy report: (\d+) record, (\d+) array and (\d+) cell copies; (\d+) string (?:escape )?cop(?:y|ies)(?:; \d+ moves? of owned (?:arrays|values))?', summaries[0])
    if summary is None:
        sys.stderr.write('copy inventory is incomplete: malformed summary\n')
        return 1
    reported = dict(zip(('record', 'array', 'cell', 'string'), map(int, summary.groups())))
    actual = Counter(note['kind'] for note in notes)
    if set(reported) != {'record', 'array', 'cell', 'string'} or any(actual[kind] != count for kind, count in reported.items()) or set(actual) - set(reported):
        sys.stderr.write('copy inventory is incomplete: entries disagree with the compiler summary\n')
        return 1
    if scope_files is not None and any(not (root / note['file']).is_file() for note in notes):
        sys.stderr.write('copy inventory cannot be scoped: an entry has no resolvable source file\n')
        return 1
    if args.only:
        notes = [note for note in notes if args.only in note['file']]
    if scope_files is not None:
        # Compiler paths are relative to its cwd, not to the caller's cwd.
        # Exact resolved files prevent a sibling such as source-old/ from
        # accidentally entering a source/ budget through substring matching.
        notes = [note for note in notes if (root / note['file']).resolve() in scope_files]
    kinds = Counter(note['kind'] for note in notes)
    density = len(notes) * 1000 / source_lines if source_lines else None
    over_count = args.max_copies is not None and len(notes) > args.max_copies
    over_density = args.max_copies_per_kloc is not None and density > args.max_copies_per_kloc
    over_budget = over_count or over_density
    if args.json:
        print(json.dumps(dict(version=1, source=args.file, compiler=command, only=args.only,
                              count=len(notes), kinds=dict(kinds), notes=notes,
                              budget=args.max_copies, within_budget=not over_budget,
                              scope=str(args.scope.resolve()) if args.scope is not None else None,
                              source_lines=source_lines, copies_per_kloc=density,
                              density_budget=args.max_copies_per_kloc), indent=2))
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
    if over_count:
        sys.stderr.write(f'copy budget exceeded: {len(notes)} sites > {args.max_copies} allowed\n')
    if over_density:
        sys.stderr.write(f'copy density exceeded: {density:.3f} sites/kloc > {args.max_copies_per_kloc:g} allowed ({source_lines} physical source lines)\n')
    return int(over_budget)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
