"""Independent in-memory model of the backup script; run with --write to refresh expected.out."""
from pathlib import Path, PurePosixPath
import sys

HERE = Path(__file__).parent


def fnv(data: bytes) -> int:
    h = 14695981039346656037
    for b in data:
        h = ((h ^ b) * 1099511628211) % (1 << 64)
    return h


def inside(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return bool(parts) and '..' not in parts and not PurePosixPath(name).is_absolute()


def expected() -> str:
    out = []
    workspace: dict[str, bytes] = {}
    objects: dict[int, bytes] = {}
    manifests: list[dict[str, tuple[int, int]]] = []
    for raw in (HERE / 'stdin.txt').read_text().split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        command, *rest = line.split(' ')
        if command == 'write':
            name, text = rest[0], ' '.join(rest[1:])
            if not inside(name):
                out.append(f'refused {name}: outside the workspace')
                continue
            workspace[name] = text.encode()
            out.append(f'wrote {name}')
        elif command == 'remove':
            del workspace[rest[0]]
            out.append(f'removed {rest[0]}')
        elif command == 'backup':
            n = len(manifests) + 1
            previous = manifests[-1] if manifests else {}
            entries, stored, reused = {}, [], 0
            for name in sorted(workspace):
                data = workspace[name]
                h = fnv(data)
                entries[name] = (h, len(data))
                if h in objects:
                    reused += 1
                else:
                    objects[h] = data
                    stored.append(h)
            removed = sum(1 for name in previous if name not in entries)
            manifests.append(entries)
            out.append(f'snapshot {n}: {len(entries)} files, {len(stored)} stored, {reused} reused, {removed} removed')
            out.extend(f'  stored {h} ({len(objects[h])} bytes)' for h in stored)
        elif command == 'restore':
            n, name = int(rest[0]), rest[1]
            entry = manifests[n - 1].get(name)
            if entry is None:
                out.append(f'snapshot {n} has no {name}')
                continue
            out.append(f'restored {name} from snapshot {n}: {objects[entry[0]].decode()}')
        elif command == 'verify':
            checked = sum(len(m) for m in manifests)
            out.append(f'verified {checked} entries in {len(manifests)} snapshots, 0 damaged')
    count = len(manifests)
    out.append(f'leases opened {count}, released {count}')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    path = HERE / 'expected.out'
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('137 oracle: matched')
