"""Independent sequential model; run with --write to refresh expected.out."""
from pathlib import Path
import sys


def expected():
    batch = [(101, 'thumbnail', 3), (102, 'invoice', 8), (103, 'index', 5),
             (104, 'preview', 2), (105, 'archive', 13), (106, 'manifest', 1)]
    lines = ['snapshot 42', f'rate 7 admitted {len(batch)} received {len(batch)}']
    for i, (job, name, units) in enumerate(batch):
        lines.append(f'{job} {"AB"[i % 2]} {name} units={units} cost={units * 7}')
    lines += [f'audited {len(batch)} drained true', 'late 0 source open true']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    path = Path(__file__).with_name('expected.out')
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('133 oracle: matched')
