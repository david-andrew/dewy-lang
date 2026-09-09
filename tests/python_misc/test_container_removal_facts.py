"""Key identity does not prove two runtime keys have different values."""

import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir
from dewy.semantic.analyze.effects import _iter_children
from dewy.semantic.errors import UserError


def checked(text):
    return check.typecheck_and_resolve(SrcFile(None, text))


@pytest.mark.parametrize('text', [
    "let d=['a' -> 1]\nlet k:string='a'\nd.pop(k default=0);\nd['a']",
    "let d=['a' -> 1]\nlet k:string='a'\nif k in? d {d.pop('a'); d[k];}",
    "let d:dict<'a'|'b' int64>=['a' -> 1 'b' -> 2]\nd.pop('a');\nlet k:'a'|'b'='a'\nd[k]",
    "let s=set[1 2]\nlet k:int64=1\ns.pop(k default=none);\ns.pop(1)",
])
def test_removal_forgets_keys_that_may_equal_the_removed_value(text):
    with pytest.raises(UserError, match='key is not proven present'):
        checked(text)


def test_removal_keeps_distinct_constant_keys_at_their_slots():
    root = checked("let d=['a' -> 1 'b' -> 2]\nd.pop('a');\nd['b']")

    def walk(node):
        yield node
        for child in _iter_children(node):
            yield from walk(child)

    lookup, = [node for node in walk(root) if isinstance(node, hir.DictLookup)]
    assert lookup.proven and lookup.static_position == 1
