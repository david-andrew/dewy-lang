"""Regenerate the C syntax-parser seed; ordinary core builds do not need this."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from tools.sloppy_core.build import CORE, HERE, ROOT, identity


def regenerate(dewy: Path, udewy: Path, output: Path) -> None:
    dewy, udewy, output = dewy.resolve(strict=True), udewy.resolve(strict=True), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DEWY_', 'SLOPPY_'))}
    env.update(DEWY_LIBRARY_ROOT=str(ROOT / 'library'), DEWY_UDEWY=str(udewy))
    command = [dewy, '--target', 'c', '-c', HERE / 'parse.dewy']
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='dewy-parser-seed-') as temporary:
        work = Path(temporary)
        result = subprocess.run(command, cwd=work, env=env, capture_output=True,
                                text=True, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        sources = list(work.rglob('parse.c'))
        if len(sources) != 1:
            raise RuntimeError(f'expected one generated parse.c, found {sources}')
        source = sources[0]
        archive = output / 'dewy_parse.c.gz'
        archive.write_bytes(gzip.compress(source.read_bytes(), mtime=0))
        inputs = [HERE / 'parse.dewy', *sorted((ROOT / 'dewy/bootstrap/parser').glob('*.dewy')),
                  *sorted((ROOT / 'library').rglob('*.dewy')), *sorted((ROOT / 'library/unicode').glob('*.bin'))]
        manifest = {
            'description': 'Generated C syntax-parser bootstrap; decompress and compile, no Dewy seed needed.',
            'c_sha256': identity(source), 'gzip_sha256': identity(archive),
            'dewy_seed_sha256': identity(dewy), 'udewy_seed_sha256': identity(udewy),
            'source_snapshot_sha256': {str(p.relative_to(ROOT)): identity(p) for p in inputs},
            'generation': {'command': [str(arg) for arg in command], 'returncode': result.returncode,
                           'wall_seconds': time.perf_counter() - started},
        }
        (output / 'dewy_parse.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--dewy', type=Path, required=True)
    cli.add_argument('--udewy', type=Path, required=True)
    cli.add_argument('--output', type=Path, default=CORE / 'bootstrap')
    args = cli.parse_args()
    regenerate(args.dewy, args.udewy, args.output)
