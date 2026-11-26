"""Value the stock still on the shelf from the newest receipts backwards."""
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
import re
import sys

HERE = Path(__file__).parent


@dataclass
class Stock:
    receipts: list = field(default_factory=list)
    balance: int = 0
    revenue: int = 0
    sold: int = 0
    damage: int = 0

    def lots(self):
        remaining = self.balance
        newest = []
        for units, price in reversed(self.receipts):
            if not remaining:
                break
            used = min(units, remaining)
            newest.append((used, price))
            remaining -= used
        return list(reversed(newest))


def value(lots):
    return sum(units * price for units, price in lots)


def money(cents):
    dollars, change = divmod(abs(cents), 100)
    return f"{'-' if cents < 0 else ''}{dollars}.{change:02d}"


def post(book, words):
    op = words[0]
    if op not in ('buy', 'sell', 'damage'):
        return 'unknown operation'
    if len(words) != (3 if op == 'damage' else 4):
        return 'wrong field count'
    _, name, count, *price = words
    if not re.fullmatch('[a-z][a-z0-9-]*', name):
        return f'invalid sku {name}'
    if not re.fullmatch(r'[0-9]+', count) or int(count) == 0:
        return 'invalid quantity'
    units = int(count)
    if price:
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', price[0]):
            return 'invalid price'
        unit_price = int(Fraction(price[0]) * 100)
    if op == 'buy':
        stock = book.setdefault(name, Stock())
        stock.receipts.append((units, unit_price))
        stock.balance += units
        return
    stock = book.get(name, Stock())
    if units > stock.balance:
        return f'{name} has {stock.balance}, needs {units}'
    before = value(stock.lots())
    stock.balance -= units
    released = before - value(stock.lots())
    if op == 'damage':
        stock.damage += released
    else:
        stock.sold += released
        stock.revenue += unit_price * units


def report(book, accepted, rejected):
    lines = [f'stockroom after {accepted} postings ({rejected} rejected)']
    for name, stock in sorted(book.items()):
        lots = stock.lots()
        lines.append(f'  {name}: {stock.balance} units, value {money(value(lots))}')
        lines.extend(f'    {units} @ {money(price)}' for units, price in lots)
        lines.append(f'    sales {money(stock.revenue)}, cost {money(stock.sold)}, damage {money(stock.damage)}')
    bought = sum(value(s.receipts) for s in book.values())
    held = sum(value(s.lots()) for s in book.values())
    released = sum(s.sold + s.damage for s in book.values())
    sales = sum(s.revenue for s in book.values())
    lines.extend((f'purchases {money(bought)}, held {money(held)}, released {money(released)}',
                  f'net margin {money(sales - released)}', f'unreconciled {money(bought - held - released)}'))
    return lines


def run():
    book, out = {}, []
    accepted = rejected = 0
    for n, raw in enumerate((HERE / 'stdin.txt').read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line == 'report':
            out.extend(report(book, accepted, rejected))
        elif reason := post(book, line.split()):
            rejected += 1
            out.append(f'line {n}: {reason}')
        else:
            accepted += 1
    out.extend(report(book, accepted, rejected))
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    expected = HERE / 'expected.out'
    if sys.argv[1:] == ['--write']:
        expected.write_text(run())
    elif expected.read_text() != run():
        sys.exit('expected.out differs from the FIFO valuation')
