"""Model the spool as dated message streams, without performing file operations."""
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).parent


def filename(key):
    stream, day = key
    return f'{stream}.{day}.log' if day else f'{stream}.log'


def inventory(streams):
    count = 0
    out = []
    for key, messages in sorted(streams.items(), key=lambda pair: filename(pair[0])):
        count += len(messages)
        out.append(f'  {filename(key)}: {len(messages)} [{messages[0]} / {messages[-1]}]')
    return [*out, f'inventory: {len(streams)} files, {count} events']


def rotation(streams, mode, day, days):
    rolls, blocked, expired = [], [], []
    for key in sorted(streams, key=filename):
        stream, stamp = key
        if stamp is None:
            if (stream, day) in streams:
                blocked.append(key)
            else:
                rolls.append(key)
        elif stamp <= day - timedelta(days=days):
            expired.append(key)
    out = [f'{mode} {day}: {len(rolls)} rolls, {len(expired)} expired']
    for key in rolls:
        archive = (key[0], day)
        out.append(f'  roll {filename(key)} -> {filename(archive)}')
        if mode == 'rotate':
            streams[archive] = streams.pop(key)
    for key in expired:
        out.append(f'  expire {filename(key)}')
        if mode == 'rotate':
            del streams[key]
    out.extend(f"  keep {filename(key)}: today's archive exists" for key in blocked)
    return out


def run():
    entry = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]
    days = int(entry['args'][1])
    streams, out = defaultdict(list), []
    for raw in (HERE / 'stdin.txt').read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        command, *args = line.split(' ')
        if command == 'list':
            out.extend(['list takes no arguments'] if args else inventory(streams))
        elif command == 'write':
            if len(args) < 2:
                out.append('write needs a stream and message')
            elif not re.fullmatch('[a-z][a-z0-9_-]*', args[0]):
                out.append(f'invalid stream {args[0]}')
            else:
                streams[args[0], None].append(' '.join(args[1:]))
        elif command in ('rotate', 'preview'):
            if len(args) != 1:
                out.append('rotation needs an ISO date')
                continue
            try:
                day = date.fromisoformat(args[0])
                if day.isoformat() != args[0]:
                    raise ValueError
            except ValueError:
                out.append(f'invalid rotation date {args[0]}')
            else:
                out.extend(rotation(streams, command, day, days))
        else:
            out.append(f'unknown request {line}')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the log spool model')
