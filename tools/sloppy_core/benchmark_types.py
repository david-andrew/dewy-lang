"""Measure fresh type-checking as the number of distinct record types grows."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from tools.sloppy_core.benchmark_compile import WORKLOADS, measure, positive


def record_source(count: int) -> str:
    parts = ['struct Box[T]:\n    value: T\n']
    for i in range(count):
        parts.append(f'struct Record{i}:\n    value: int\n'
                     f'make{i} = (x: int) -> Box[Record{i}]: Box(Record{i}(x))\n')
    parts.append('main = ():\n    total = 0\n')
    for i in range(count):
        parts.append(f'    total += make{i}({i}).value.value\n')
    parts.append('    print(total)\n')
    return ''.join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--count', type=positive, action='append')
    parser.add_argument('--samples', type=positive, default=7)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    counts = args.count or [500, 1000, 2000]
    compilers = {'baseline': args.baseline.resolve(strict=True),
                 'candidate': args.compiler.resolve(strict=True)}
    with tempfile.TemporaryDirectory(prefix='dewy-types-benchmark-') as directory:
        names = []
        for count in dict.fromkeys(counts):
            name = f'records-{count}'
            source = Path(directory) / f'{name}.jo'
            source.write_text(record_source(count))
            WORKLOADS[name] = ('check', str(source))
            names.append(name)
        result = measure(compilers, names, args.samples, 1)
    result['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['scope'] = ('Synthetic type-check scaling: each distinct record is wrapped in the '
                       'same generic Box, constructed by a function called from main. '
                       'No code generation or program runtime is timed.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
