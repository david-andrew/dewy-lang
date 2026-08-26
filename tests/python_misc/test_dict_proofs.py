import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import UserError


def _check(body: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, f'let main = ():>int64 => {{\n{body}\n    return 0\n}}'))


def _lookups(root: hir.Block) -> list[hir.DictLookup]:
    found: list[hir.DictLookup] = []

    def walk(value: object) -> None:
        if isinstance(value, hir.DictLookup):
            found.append(value)
        if isinstance(value, hir.AST):
            for name in value.__dataclass_fields__:
                walk(getattr(value, name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, hir.ObjectField):
            walk(value.value)

    walk(root)
    return found


def test_unproven_key_is_rejected_with_the_get_hint() -> None:
    with pytest.raises(UserError, match='dictionary key is not proven present') as info:
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let v = d[k]")
    assert 'd.get(key)' in str(info.value.report)


def test_literal_store_guard_and_iteration_prove_keys() -> None:
    root = _check(
        "    let d = ['a' -> 1 'b' -> 2]\n"
        "    let x = d['b']\n"
        "    d['c'] = 3\n"
        "    let y = d['c']\n"
        "    let k:string = 'q'\n"
        "    if k in? d { let z = d[k] }\n"
        "    loop [key value] in d { let w = d[key] }"
    )
    lookups = _lookups(root)
    assert [lookup.proven for lookup in lookups] == [True, True, True, True]
    assert lookups[0].static_position == 1            # literal entry index
    assert lookups[1].position is not None            # the store's position local
    assert lookups[2].position is not None            # the guard's search position
    assert lookups[3].position is None                # iteration: present, searched
    assert all(lookup.type == 'int64' for lookup in lookups)


def test_get_is_optional_or_defaulted() -> None:
    root = _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let m = d.get(k)\n    let n = d.get(k 9)")
    maybe, defaulted = _lookups(root)
    assert not maybe.proven and ty.optional_payload(maybe.type) == 'int64'
    assert defaulted.default is not None and defaulted.type == 'int64'


def test_reassignment_drops_key_facts() -> None:
    with pytest.raises(UserError, match='not proven present'):
        _check("    let d = ['a' -> 1]\n    let k:string = 'a'\n    d['q'] = 2\n    let k2:string = 'q'\n    let e = ['z' -> 0]\n    d = e\n    let v = d['q']")
    with pytest.raises(UserError, match='not proven present'):
        _check("    let d = ['a' -> 1]\n    let k:string = 'a'\n    if k in? d { k = 'zz' let v = d[k] }")


def test_key_facts_join_across_branches() -> None:
    # proven on every path: fine; proven on one path only: rejected
    _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    if k in? d { d[k] = 2 } else { d[k] = 3 }\n    let v = d[k]")
    with pytest.raises(UserError, match='not proven present'):
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let flag:bool = true\n    if flag { d[k] = 2 }\n    let v = d[k]")


def test_pop_needs_a_proven_key_and_keeps_positions() -> None:
    with pytest.raises(UserError, match='not proven present'):
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let v = d.pop(k)")
    # a removal leaves a tombstone: the other keys stay proven at their entries
    root = _check("    let d = ['a' -> 1 'b' -> 2]\n    let x = d.pop('a')\n    let y = d['b']")
    lookups = _lookups(root)
    assert lookups[0].proven and lookups[0].static_position == 1


def test_stores_and_iteration_forget_positions() -> None:
    # a store may resize (compacting entries); iteration compacts too
    root = _check("    let d = ['a' -> 1 'b' -> 2]\n    d['c'] = 3\n    let y = d['b']\n    loop [k v] in d { }\n    let z = d['c']")
    lookups = _lookups(root)
    assert lookups[0].proven and lookups[0].static_position is None and lookups[0].position is None
    assert lookups[1].proven and lookups[1].position is None


def test_clear_forgets_every_key() -> None:
    with pytest.raises(UserError, match='not proven present'):
        _check("    let d = ['a' -> 1]\n    d.clear\n    let v = d['a']")


def test_pop_with_a_default_needs_no_proof() -> None:
    root = _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let v = d.pop(k default=0)")
    removes = [item for item in root.items[0].expr.body.items if isinstance(item, hir.Declare) and item.name == 'v']
    assert isinstance(removes[0].expr, hir.DictRemove) and removes[0].expr.default is not None
    assert removes[0].expr.type == 'int64'
    with pytest.raises(UserError, match='not proven present') as info:
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let v = d.pop(k)")
    assert 'default=' in str(info.value.report)
