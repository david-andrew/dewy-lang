"""Compare hosted and native copy inventories site by site.

Usage:
  python tools/copy_report.py --json FILE > hosted.json
  python tools/copy_report.py --json --compiler NATIVE FILE > native.json
  python tools/copy_parity.py hosted.json native.json [--classes CLASSES.json] [--list N]

Both compilers print the same `copy:` notes for the same program (closure
matrix row C3). A note is identified by file, row, kind and site; reasons are
compared after collapsing quoted names. Every difference is one of:

- `hosted-only`: the hosted compiler copies where native does not;
- `native-only`: native copies where hosted does not;
- `reason`: both copy at the same boundary, for differently stated reasons;
- `paired`: both copy on that row, at differently named boundaries.

Differences are grouped by kind, site and normalized reason. `--classes` names
a JSON list of `{"class", "explanation", "side", "kind", "site", "reason"}`
entries, where `side`/`kind`/`site`/`reason` are regular expressions that must
all match (`reason` against the normalized reason; for `reason` and `paired`
differences, site and reason read `hosted => native`). The first matching entry classifies a
difference. The exit status is nonzero when any difference is unclassified, so
the comparison can gate that every divergence has a recorded explanation.
"""

from __future__ import annotations

import json
import re
import sys
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def normalized(reason: str) -> str:
    return re.sub(r'`[^`]*`', '`_`', reason or '')


def relative(file: str) -> str:
    path = Path(file)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return file


def load(path: str) -> Counter:
    notes = json.loads(Path(path).read_text())['notes']
    return Counter((relative(note['file']), int(note['row']), note['kind'], note['site'], normalized(note['reason'])) for note in notes)


def differences(hosted: Counter, native: Counter) -> list[dict]:
    """Row-level differences after removing identical notes.

    Notes left on the same file, row and kind pair up as one `paired`
    difference whose site and reason read `hosted => native`: both compilers
    copy there, but describe the boundary differently. Surplus notes on either
    side are `hosted-only` or `native-only`.
    """
    common = hosted & native
    left = hosted - common
    right = native - common
    rows: dict = {}
    for side, notes in (('h', left), ('n', right)):
        for (file, row, kind, site, reason), count in notes.items():
            rows.setdefault((file, row, kind), {'h': [], 'n': []})[side].extend([(site, reason)] * count)
    result = []
    for (file, row, kind), sides in sorted(rows.items()):
        lefts, rights = sorted(sides['h']), sorted(sides['n'])
        while lefts and rights:
            (hs, hr), (ns, nr) = lefts.pop(), rights.pop()
            side = 'reason' if hs == ns else 'paired'
            site = hs if hs == ns else f'{hs} => {ns}'
            result.append(dict(side=side, file=file, row=row, kind=kind, site=site, reason=f'{hr} => {nr}'))
        for site, reason in lefts:
            result.append(dict(side='hosted-only', file=file, row=row, kind=kind, site=site, reason=reason))
        for site, reason in rights:
            result.append(dict(side='native-only', file=file, row=row, kind=kind, site=site, reason=reason))
    return result


def classify(difference: dict, classes: list[dict]) -> str | None:
    for entry in classes:
        if all(re.search(entry.get(field, ''), difference[field]) for field in ('side', 'kind', 'site', 'reason')):
            return entry['class']
    return None


def main(argv: list[str]) -> int:
    parser = ArgumentParser()
    parser.add_argument('hosted')
    parser.add_argument('native')
    parser.add_argument('--classes', help='JSON list of recorded difference classes')
    parser.add_argument('--list', type=int, default=0, help='print up to N unclassified differences')
    args = parser.parse_args(argv)
    hosted, native = load(args.hosted), load(args.native)
    found = differences(hosted, native)
    classes = json.loads(Path(args.classes).read_text()) if args.classes else []
    print(f'hosted {sum(hosted.values())} copies, native {sum(native.values())}; '
          f'{sum((hosted & native).values())} identical, {len(found)} differences')
    by_class: Counter = Counter()
    unclassified: Counter = Counter()
    examples: dict = {}
    for difference in found:
        name = classify(difference, classes)
        if name is None:
            key = (difference['side'], difference['kind'], difference['site'], difference['reason'])
            unclassified[key] += 1
            examples.setdefault(key, f"{difference['file']}:{difference['row']}")
        else:
            by_class[name] += 1
    for name, count in by_class.most_common():
        print(f'{count:6d}  {name}')
    if unclassified:
        print(f'{sum(unclassified.values())} unclassified differences in {len(unclassified)} groups')
        for (side, kind, site, reason), count in unclassified.most_common(args.list or 0):
            print(f'{count:6d}  {side} {kind} [{site}] {reason}  (e.g. {examples[(side, kind, site, reason)]})')
    return 1 if unclassified else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
