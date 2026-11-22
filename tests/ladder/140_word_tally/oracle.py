"""Independent word tally over the same command line; run with --write to refresh expected.out."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent


def command_line():
    entry = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]
    return [word.replace('{dir}', str(HERE)) for word in entry['args']]


def words_of(line):
    found, current = [], ''
    for ch in line:
        if ch.isalnum() or ch in "'-":
            current += ch
        elif current:
            found.append(current)
            current = ''
    if current:
        found.append(current)
    return [w.strip("'-") for w in found if w.strip("'-")]


def run(argv):
    top, min_length, ignore_case, exclude, out, files, only = 5, 1, False, set(), None, [], False
    for word in argv:
        if only or not (word.startswith('-') or '=' in word):
            files.append(word)
        elif word == '--':
            only = True
        elif word in ('-i', '--ignore-case'):
            ignore_case = True
        else:
            name, value = word.split('=', 1)
            if name == 'top':
                top = int(value)
            elif name == 'min_length':
                min_length = int(value)
            elif name == 'out':
                out = value
            elif name == 'exclude':
                exclude |= {w.lower() for w in value.split(',')}
    lines, counts, stats, skipped = [], {}, [], []
    for name in files:
        path = Path(name)
        if not path.exists():
            skipped.append(path.name)
            continue
        data = path.read_bytes()
        text = data.decode()
        rows = text.split('\n')
        if rows and rows[-1] == '':
            rows.pop()
        s = [path.name, 0, 0, len(data), 0, 0]
        for number, raw in enumerate(rows, 1):
            line = raw[:-1] if raw.endswith('\r') else raw
            s[1] += 1
            if len(line) > s[4]:
                s[4], s[5] = len(line), number
            for word in words_of(line):
                s[2] += 1
                key = word.lower() if ignore_case else word
                if len(key) < min_length or key.lower() in exclude:
                    continue
                counts[key] = counts.get(key, 0) + 1
        stats.append(s)
    row = lambda a, b, c, d, e: f'{a:<14}{b:>6}{c:>7}{d:>7}{e:>12}'
    lines.append(row('file', 'lines', 'words', 'bytes', 'longest'))
    for s in stats:
        lines.append(row(s[0], s[1], s[2], s[3], f'{s[4]} @{s[5]}'))
    lines.append(row('total', sum(s[1] for s in stats), sum(s[2] for s in stats), sum(s[3] for s in stats), '-'))
    if skipped:
        lines.append(f'skipped: {", ".join(skipped)}')
    case = 'any case' if ignore_case else 'exact case'
    lines.append(f'top {top} of {len(counts)} words ({case}, at least {min_length} long):')
    ranked = sorted(sorted(counts.items()), key=lambda kv: -kv[1])[:top]
    for word, n in ranked:
        lines.append(f'  {n:>3}  {word}')
    if out is not None:
        table = ['file\tlines\twords\tbytes\tlongest']
        table += [f'{s[0]}\t{s[1]}\t{s[2]}\t{s[3]}\t{s[4]}@{s[5]}' for s in stats]
        table += [f'word\t{w}\t{n}' for w, n in ranked]
        text = '\n'.join(table) + '\n'
        lines.append(f'wrote {len(table)} rows ({len(text.encode())} bytes) to {Path(out).name}; reread matches')
    return '\n'.join(lines) + '\n'


def main():
    output = run(command_line())
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(output)
    elif expected.read_text() != output:
        sys.exit('expected.out differs from the oracle')


if __name__ == '__main__':
    main()
