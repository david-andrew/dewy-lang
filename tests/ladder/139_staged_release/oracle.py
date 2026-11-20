"""Independent model of the intended release behavior; run with --write to refresh expected.out."""
from pathlib import Path, PurePosixPath
import sys

HERE = Path(__file__).parent


def expected():
    plans = []
    for raw in (HERE / 'stdin.txt').read_text().split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        kind, *rest = line.split(' ')
        if kind == 'release':
            plans.append((int(rest[0]), []))
        elif kind == 'file' and plans and len(rest) >= 2:
            plans[-1][1].append((rest[0], ' '.join(rest[1:])))
    out, published = [], []
    for version, files in plans:
        out.append(f'release v{version}: {len(files)} files')
        staged = 0
        refused = None
        for name, _ in files:
            if '..' in PurePosixPath(name).parts or PurePosixPath(name).is_absolute():
                refused = name
                break
            staged += 1
        if refused is None:
            out.append(f'  published releases/v{version} with {staged} files')
            published.append(f'v{version}')
        else:
            out.append(f'  abandoned v{version}: removed {staged} staged files')
            out.append(f'  refused: {refused} leaves the release')
    out.append(f'published: {" ".join(sorted(published))}')
    out.append('staging left: 0')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    path = HERE / 'expected.out'
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('139 oracle: matched')
