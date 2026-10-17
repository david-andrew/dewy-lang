"""Measure fresh type-checking as the number of distinct generic types grows."""
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


def generic_source(count: int) -> str:
    parts = ['identity=<T>(value:T):>T=>value\n']
    for i in range(count):
        parts.append(f'Record{i}:type=[value:int64]\n')
    parts.append('main=()=>{let total:int64=0\n')
    for i in range(count):
        parts.append(f'total+=identity(Record{i}[{i}]).value\n')
    parts.append('printl(total)}\n')
    return ''.join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--count', type=positive, action='append')
    parser.add_argument('--kind', choices=['records', 'functions'], default='records')
    parser.add_argument('--samples', type=positive, default=7)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    counts = args.count or [500, 1000, 2000]
    compilers = {'baseline': args.baseline.resolve(strict=True),
                 'candidate': args.compiler.resolve(strict=True)}
    with tempfile.TemporaryDirectory(prefix='dewy-types-benchmark-') as directory:
        names = []
        for count in dict.fromkeys(counts):
            name = f'{args.kind}-{count}'
            suffix = 'dewy' if args.kind == 'functions' else 'jo'
            source = Path(directory) / f'{name}.{suffix}'
            source.write_text(generic_source(count) if args.kind == 'functions' else record_source(count))
            WORKLOADS[name] = ('check', str(source))
            names.append(name)
        result = measure(compilers, names, args.samples, 1)
    result['generator_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    description = ('passed to the same generic identity function' if args.kind == 'functions'
                   else 'wrapped in the same generic Box, constructed by a function called from main')
    result['scope'] = (f'Synthetic type-check scaling: each distinct record is {description}. '
                       'No code generation or program runtime is timed.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
