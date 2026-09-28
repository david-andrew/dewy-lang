"""Attribute a native Dewy program's arena allocations to source statements.

Usage:
  python tools/allocation_sites.py instrument PROGRAM.debug.udewy OUT.udewy
  udewy -c OUT.udewy                    # build the instrumented program
  INSTRUMENTED ARGS... 3> counts.bin    # run it; the table goes to fd 3
  python tools/allocation_sites.py report OUT.udewy counts.bin [--top N]

The input is the µDewy text of a debug build, which keeps function names and
`# @loc` markers: `DEWY_EMIT=udewy dewy debug --build PROGRAM.dewy` leaves it
next to the executable as `PROGRAM.debug.udewy`. `instrument` stores a site
number before every statement of every named function. The arena entry points
(`_arena_alloc` and its fixed size-class variants) then add one allocation and
its requested bytes to that site's slot. Helpers such as `_copy_objectN` or
`_new_arrayN` have no named-function prefix, so their allocations count
against the calling statement. Requested bytes are slightly below the arena's
own `allocated` counter, which counts size-class widths.

`report` groups the counts by mechanism (the helper a statement calls), by
source file, by function and by statement, and splits array growth by the
average size of a growth step. The measurement for the compiler's own
sources is recorded in `dewy/bootstrap/PERFORMANCE.md`.
"""

from __future__ import annotations

import pickle
import re
import struct
import sys
from argparse import ArgumentParser
from collections import Counter

MAX_SITES = 4_000_000
DIGITS = {f'e2828{d}': str(d) for d in range(10)}  # UTF-8 subscript digits
NAMED = re.compile(r'^_f\d+_[a-z]')
FIXED_ENTRY = re.compile(r'let _f\d+___dewy_encoded_5f6172656e615f616c6c6f63((?:e2828[0-9])+) = \(\):>int64 => \{\n')
SIZED_ENTRY = re.compile(r'let _f\d+__arena_alloc = \((_b\d+_size):int64\):>int64 => \{\n')
MECHANISMS = [
    ('record copy', r'_copy_object\d+\('),
    ('union cell copy', r'_copy_cell\d+\('),
    ('new union cell', r'_new_cell\d+\('),
    ('array growth', r'_push\d+\(|_reserve_array\d+\(|_extend\d*\('),
    ('shared array detach', r'_unique_array\d+\('),
    ('dictionary index rebuild', r'_rebuild_dict\d+\('),
    ('new array descriptor', r'_new_array\d+\('),
    ('string storage', r'native_string|_quoted\(|string'),
    ('new record or union', r'_alloc\d+\('),
    ('direct arena request', r'_arena_alloc'),
]
GROWTH = re.compile(MECHANISMS[3][1])


def instrument(source: str, target: str) -> None:
    lines = open(source).read().split('\n')
    out: list[str] = []
    sites: dict[int, tuple[str, str, str]] = {}
    function: str | None = None
    location = ''
    for line in lines:
        if line.startswith('let ') and '=> {' in line:
            name = line.split(' = ')[0][4:]
            function = name if NAMED.match(name) else None
        elif line.startswith('}'):
            function = None
        else:
            text = line.strip()
            if text.startswith('# @loc '):
                location = text[len('# @loc '):]
            elif function and text and not text.startswith('}') and not text.startswith('else'):
                sites[len(sites) + 1] = (function, location, text[:160])
                indent = line[:len(line) - len(line.lstrip())]
                out.append(f'{indent}__site = {len(sites)}')
        out.append(line)
    if len(sites) >= MAX_SITES:
        raise SystemExit(f'{len(sites)} statements exceed the {MAX_SITES} site table')
    text = '\n'.join(out)
    counter = f'''let __site:int64 = 0
let __site_table:int64 = 0
let __site_count = (size:int64):>void => {{
    if __site_table =? 0 {{
        let anywhere:int64 = 0 - 1
        __site_table = __syscall6__(9 0 {MAX_SITES * 16} 3 34 anywhere 0)
    }}
    let slot:int64 = __site_table + (__site * 16)
    __store_i64__(__load_i64__(slot) + 1 slot)
    __store_i64__(__load_i64__(slot + 8) + size slot + 8)
    return void
}}
'''
    anchor = text.index('\nlet _none_cell1')
    text = text[:anchor + 1] + counter + text[anchor + 1:]
    patched = 0

    def fixed(match: re.Match[str]) -> str:
        nonlocal patched
        patched += 1
        size = ''.join(DIGITS[d] for d in re.findall(r'e2828[0-9]', match.group(1)))
        return match.group(0) + f'    __site_count({size})\n'

    def sized(match: re.Match[str]) -> str:
        nonlocal patched
        patched += 1
        return match.group(0) + f'    __site_count({match.group(1)})\n'

    text = FIXED_ENTRY.sub(fixed, text)
    text = SIZED_ENTRY.sub(sized, text)
    if not patched:
        raise SystemExit('no arena allocation entry points found; is this a debug build?')
    text = re.sub(r'(?m)^let main = \(', 'let __site_main = (', text, count=1)
    text += f'''
let main = (__dewy_argc:int64 __dewy_argv:int64):>int64 => {{
    let result:int64 = __site_main(__dewy_argc __dewy_argv)
    __syscall3__(1 3 __site_table {MAX_SITES * 16})
    return result
}}
'''
    open(target, 'w').write(text)
    pickle.dump(sites, open(target + '.sites', 'wb'))
    print(f'{len(sites)} statement sites, {patched} allocation entry points')


def report(program: str, table: str, top: int) -> None:
    sites: dict[int, tuple[str, str, str]] = pickle.load(open(program + '.sites', 'rb'))
    data = open(table, 'rb').read()
    words = struct.unpack(f'<{len(data) // 8}q', data)
    rows = []
    for site, (function, location, statement) in sites.items():
        count, size = words[2 * site], words[2 * site + 1]
        if count:
            rows.append((size, count, re.sub(r'^_f\d+_', '', function), location, statement))
    total_bytes = sum(row[0] for row in rows)
    total_count = sum(row[1] for row in rows)
    print(f'{total_count / 1e6:.1f} M allocations, {total_bytes / 1e9:.2f} GB requested')

    def show(title: str, bytes_by: Counter, count_by: Counter, limit: int) -> None:
        print(f'\n{title}')
        for key, size in bytes_by.most_common(limit):
            print(f'{size / 1e9:7.2f} GB {100 * size / total_bytes:5.1f}% {count_by[key] / 1e6:7.1f} M  {key}')

    def mechanism(statement: str) -> str:
        for name, pattern in MECHANISMS:
            if re.search(pattern, statement):
                return name
        return 'inside a named call'

    groups: dict[str, tuple[Counter, Counter]] = {name: (Counter(), Counter()) for name in ('mechanism', 'file', 'function', 'growth')}
    for size, count, function, location, statement in rows:
        path = location.rsplit(':', 2)[0]
        for name, key in (('mechanism', mechanism(statement)), ('file', path), ('function', f'{function} ({path})')):
            groups[name][0][key] += size
            groups[name][1][key] += count
        if GROWTH.search(statement):
            average = size / count
            bucket = ('first 8-slot buffer (average <= 72 B)' if average <= 72 else
                      'average 72 B - 1 KB' if average <= 1024 else
                      'average 1 KB - 64 KB' if average <= 65536 else 'average > 64 KB')
            groups['growth'][0][bucket] += size
            groups['growth'][1][bucket] += count
    show('by mechanism', *groups['mechanism'], 20)
    show('array growth by average step per site', *groups['growth'], 4)
    show('by file', *groups['file'], top)
    show('by function', *groups['function'], top)
    print('\nby statement')
    for size, count, function, location, statement in sorted(rows, reverse=True)[:top]:
        print(f'{size / 1e9:6.2f} GB {count / 1e6:6.1f} M {size / count:8.0f} B  {function} {location}\n          {statement[:120]}')


def main(argv: list[str]) -> int:
    parser = ArgumentParser(description=__doc__.split('\n')[0])
    commands = parser.add_subparsers(dest='command', required=True)
    first = commands.add_parser('instrument')
    first.add_argument('source')
    first.add_argument('target')
    second = commands.add_parser('report')
    second.add_argument('program', help='the instrumented .udewy (its .sites file sits beside it)')
    second.add_argument('table', help='the table the instrumented program wrote to fd 3')
    second.add_argument('--top', type=int, default=30)
    args = parser.parse_args(argv)
    if args.command == 'instrument':
        instrument(args.source, args.target)
    else:
        report(args.program, args.table, args.top)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
