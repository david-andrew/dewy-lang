"""Independent inventory arithmetic and Python formatting; --write refreshes output."""
from pathlib import Path
import sys


def expected():
    items = [(42, 'USB adapter', 12, 1299), (255, 'Desk lamp', 3, 4595),
             (4096, 'Cable reel', 1200, 75), (7, 'Notebook', 48, 250)]
    def money(cents):
        whole, fraction = divmod(cents, 100)
        return f'{whole:,}.{fraction:02d}'
    def stock(item):
        sku, name, qty, cents = item
        return ' | '.join([f'{sku:#06x}', f'{name:<14}', f'{qty:>8}',
                           f'{money(cents):>10}', f'{money(qty*cents):>12}'])
    lines = [' | '.join(['SKU'.ljust(6), 'ITEM'.ljust(14), 'QTY'.rjust(8),
                         'EACH'.rjust(10), 'VALUE'.rjust(12)]),
             'Warehouse north / INVENTORY', stock(items[0]), stock(items[1]),
             '# Prices in USD; stock counted at close', stock(items[2]), stock(items[3])]
    units = sum(qty for _, _, qty, _ in items)
    value = sum(qty*cents for _, _, qty, cents in items)
    lines += [f'TOTAL lines={len(items)} units={units:,} value={money(value)}', 'formatter-v1']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    path = Path(__file__).with_name('expected.out')
    if '--write' in sys.argv:
        path.write_text(expected())
    else:
        assert path.read_text() == expected()
        print('134 oracle: matched')
