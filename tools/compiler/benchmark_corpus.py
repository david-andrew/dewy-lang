"""Measure compilation scaling using distinct executable language conformance cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from tools.compiler.benchmark_compile import ROOT, positive
from tools.compiler.benchmark_throughput import BUILD_WORKLOADS, measure


def prepare(directory: Path, cases: dict[str, str]) -> Path:
    """Keep each case's module scope and bound the generated driver functions."""
    parts = []
    for i, (name, source) in enumerate(cases.items()):
        (directory / f'{name}.dewy').write_text(source + '\n')
        parts.append(f'from p"{name}.dewy" import (main as case_{i})')
    for start in range(0, len(cases), 64):
        parts.append(f'group_{start}=()=>{{')
        for i in range(start, min(start + 64, len(cases))):
            parts.append(f'if case_{i}() not=?42 {{printl"failed case {i}" exit(1)}}')
        parts.append('}')
    parts.append('main=()=>{')
    parts.extend(f'group_{start}()' for start in range(0, len(cases), 64))
    parts.append(f'printl"passed {len(cases)} cases"}}')
    source = directory / 'main.dewy'
    source.write_text('\n'.join(parts) + '\n')
    return source


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('compiler', type=Path)
    cli.add_argument('--count', type=positive, action='append')
    cli.add_argument('--release', action='store_true')
    cli.add_argument('--samples', type=positive, default=5)
    cli.add_argument('--output', type=Path, required=True)
    options = cli.parse_args()
    # Use the same source strings as compiler validation, including resolved
    # fixture imports. Run with the development Python environment (pytest).
    from tests.test_core import CASES

    counts = list(dict.fromkeys(options.count or [128, 512, len(CASES)]))
    if any(count > len(CASES) for count in counts):
        cli.error(f'count exceeds the {len(CASES)} distinct available cases')
    groups = {}
    with tempfile.TemporaryDirectory(prefix='dewy-corpus-') as temporary:
        for count in counts:
            # Spread smaller samples across the full collection's feature areas.
            items = list(CASES.items())
            cases = dict(items[i * len(items) // count] for i in range(count))
            name = f'conformance-{count}'
            directory = Path(temporary) / name
            directory.mkdir()
            source = prepare(directory, cases)
            flags = ('--release',) if options.release else ()
            BUILD_WORKLOADS[name] = ('build', str(source), *flags)
            groups[name] = {
                'case_names': list(cases),
                'case_lines': sum(len(code.splitlines()) for code in cases.values()),
                'driver_lines': len(source.read_text().splitlines()),
                'source_sha256': hashlib.sha256(json.dumps(cases).encode()).hexdigest(),
            }

        def validate(name: str, binary: Path) -> None:
            # The argv case expects executable + one argument, as in the suite.
            ran = subprocess.run([binary, 'extra'], capture_output=True, text=True,
                                 timeout=30, check=True)
            count = len(groups[name]['case_names'])
            if not ran.stdout.endswith(f'passed {count} cases\n'):
                raise RuntimeError(f'{name} did not complete:\n{ran.stdout}\n{ran.stderr}')

        result = measure(options.compiler.resolve(strict=True), list(groups), options.samples, validate)
    result['corpus'] = groups
    result['corpus_file_sha256'] = hashlib.sha256(
        (ROOT / 'tests/test_core.py').read_bytes()).hexdigest()
    result['scope'] = ('Language conformance stress workload, not a representative game. '
                       'Distinct existing cases, no repeated padding. Every case is called and '
                       'its result checked once outside timed compilation. Includes generated '
                       'driver and imported library source; counts are reported separately. '
                       'Fresh processes/outputs with warm filesystem caches.')
    options.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
