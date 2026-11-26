"""Calculate one-vs-rest statistics directly from weighted review pairs."""
from collections import Counter
from fractions import Fraction
from pathlib import Path
import json
import sys

HERE = Path(__file__).parent


def percent(n, d):
    if not d:
        return 'n/a'
    whole, remainder = divmod(Fraction(1000 * n, d), 1)
    tenths = whole + (remainder >= Fraction(1, 2))
    return f'{tenths // 10}.{tenths % 10}%'


def report(name, labels, counts):
    out = [f'batch {name}', ' | '.join(['actual', *labels, 'referred'])]
    for label in labels:
        out.append(' | '.join([label, *(str(counts[label, col]) for col in [*labels, '-'])]))
    out.append('class: support, precision, recall, F1')
    for label in labels:
        hits = counts[label, label]
        positives = sum(n for (a, b), n in counts.items() if b == label)
        support = sum(n for (a, b), n in counts.items() if a == label)
        out.append(f'{label}: {support}, {percent(hits, positives)}, {percent(hits, support)}, '
                   f'{percent(2 * hits, support + positives)}')
    total = counts.total()
    referred = sum(counts[a, '-'] for a in labels)
    correct = sum(counts[a, a] for a in labels)
    assigned = total - referred
    out.extend([f'reviewed {total}, assigned {assigned}, referred {referred}',
                f'coverage {percent(assigned, total)}, accuracy {percent(correct, total)}',
                f'accuracy on assigned tickets {percent(correct, assigned)}'])
    errors = sorted(((-n, labels.index(a), labels.index(b), a, b)
                     for (a, b), n in counts.items() if a != b and b != '-'))
    if errors:
        out.append('most frequent wrong assignments:')
        out.extend(f'  {a} -> {b}: {-neg}' for neg, _, _, a, b in errors[:3])
    else:
        out.append('no wrong assignments')
    return out


def run():
    labels = json.loads((HERE.parent / 'ladder.json').read_text())['programs'][HERE.name]['args']
    rows, batch, out = Counter(), 'inbox', []
    for n, raw in enumerate((HERE / 'stdin.txt').read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('batch '):
            out.extend(report(batch, labels, rows))
            rows.clear()
            batch = line[6:].strip()
            continue
        fields = [f.strip() for f in line.split(',')]
        if len(fields) != 3:
            why = 'expected actual,prediction,count'
        elif fields[0] not in labels:
            why = 'unknown actual ' + fields[0]
        elif fields[1] not in [*labels, '-']:
            why = 'unknown prediction ' + fields[1]
        else:
            try:
                count = int(fields[2])
            except ValueError:
                why = 'invalid count'
            else:
                if count > 0:
                    rows[fields[0], fields[1]] += count
                    continue
                why = 'count must be positive'
        out.append(f'line {n}: {why}')
    out.extend(report(batch, labels, rows))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the classifier report')
