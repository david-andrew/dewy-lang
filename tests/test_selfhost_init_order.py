"""Whatever enters the compiler's import cycle first, type_layout's globals initialize before host_binds.jo binds them.

Initialization follows the import walk. If the walk reaches host_binds.jo through type_layout.dewy, the bind
runs first, type_layout's own initializers then clear it, and the first layout crashes on a null input.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / 'compiler'
ENTRIES = [COMPILER / 'main.jo'] + [path for path in sorted((ROOT / 'tests/fixtures').rglob('*.jo'))
                                    if '../compiler/' in path.read_text()]
IMPORT = re.compile(r'''(?m)^(?:use ['"]([^'"]+)['"]|(?:from|import) p"([^"]+)")''')


def initialization_order(entry):
    """What order_modules gives (check.jo): each module after what it imports, in the order it names them."""
    order, seen = [], set()

    def visit(path, trail):
        if path in seen:
            return
        seen.add(path)
        for match in IMPORT.finditer(path.read_text()):
            name = match[1] or match[2]
            target = (path.parent / name).resolve()
            if not name.startswith('@') and target.is_file():
                visit(target, (*trail, path.name))
        order.append((path.name, trail))

    visit(entry.resolve(), ())
    return order


@pytest.mark.parametrize('entry', ENTRIES, ids=lambda path: path.name)
def test_type_layout_initializes_before_host_binds(entry):
    order = initialization_order(entry)
    ranks = {name: (index, trail) for index, (name, trail) in enumerate(order)}
    if 'host_binds.jo' not in ranks:
        return
    assert ranks['type_layout.dewy'][0] < ranks['host_binds.jo'][0], ' > '.join(ranks['host_binds.jo'][1])
