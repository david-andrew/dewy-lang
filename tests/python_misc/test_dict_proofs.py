import pytest

from dewy.reporting import SrcFile
from dewy.semantic import check, hir, ty
from dewy.semantic.errors import TypeCheckError, UserError


def _check(body: str) -> hir.Block:
    return check.typecheck_and_resolve(SrcFile(None, f'let main = ():>int64 => {{\n{body}\n    return 0\n}}'))


def _nodes[T: hir.AST](root: hir.Block, kind: type[T]) -> list[T]:
    found: list[T] = []

    def walk(value: object) -> None:
        if isinstance(value, kind):
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


def _lookups(root: hir.Block) -> list[hir.DictLookup]:
    return _nodes(root, hir.DictLookup)


def test_unproven_key_is_rejected_with_the_get_hint() -> None:
    with pytest.raises(UserError, match='dictionary key is not proven present') as info:
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    let v = d[k]")
    assert 'd.get(key)' in str(info.value.report)


def test_dictionary_member_stores_establish_route_facts_and_obey_const():
    root = _check('''
    let wrapper:[inner:[entries:dict<string int64>]] = [inner=[entries=[]]]
    wrapper.inner.entries['a'] = 40
    wrapper.inner.entries['a'] += 2
    let answer = wrapper.inner.entries['a']
''')
    assert all(lookup.proven for lookup in _lookups(root))
    for declaration in (
        'const wrapper:[entries:dict<string int64>] = [entries=[]]',
        'let Wrapper:type = const [entries:dict<string int64>]\nlet wrapper:Wrapper = [entries=[]]',
    ):
        with pytest.raises(UserError, match='const dictionary|immutable record'):
            _check(declaration + "\nwrapper.entries['a'] = 1")


def test_member_key_facts_follow_the_field_value():
    prefix = "let d = ['a' -> 1]\nlet key:[name:string] = [name='a']\n"
    _check(prefix + 'if key.name in? d { let value = d.pop(key.name) }')
    for change in ("key.name = 'b'", "key = [name='b']"):
        with pytest.raises(UserError, match='key is not proven present'):
            _check(prefix + f'if key.name in? d {{ {change} let value = d[key.name] }}')


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


def test_set_literals_and_methods() -> None:
    root = _check("    let s = set[1 2 2 3]\n    s.add(4)\n    let n = s.length\n    let m = 2 in? s\n    let one = s.pop(1)\n    s.pop(9 default=none);\n    loop x in s { let y = x }")
    body = root.items[0].expr.body.items
    literal = body[0].expr
    assert isinstance(literal, hir.ObjectLiteral) and ty.set_element(literal.type) == 'int64'
    assert [f.name for f in literal.type.fields] == ['keys', 'hashes', 'indices', 'live']
    assert len(literal.fields[0].value.items) == 3  # duplicates collapse


def test_set_pop_needs_a_proof_unless_defaulted() -> None:
    with pytest.raises(UserError, match='set key is not proven present') as info:
        _check("    let s = set[1 2]\n    let k:int64 = 3\n    s.pop(k)")
    assert 'default=none' in str(info.value.report)
    root = _check("    let s = set[1 2]\n    let k:int64 = 3\n    let a = s.pop(k default=none)\n    let b = s.pop(k default=0)\n    if k in? s { s.pop(k); }")
    body = {item.name: item for item in root.items[0].expr.body.items if isinstance(item, hir.Declare)}
    assert ty.optional_payload(body['a'].expr.type) == 'int64'
    assert body['b'].expr.type == 'int64'


def test_sets_are_not_indexable_or_storable() -> None:
    with pytest.raises(UserError, match='sets are not indexable'):
        _check("    let s = set[1 2]\n    let v = s[1]")


def test_mutating_a_container_while_iterating_it_is_rejected() -> None:
    # Python raises at runtime ("changed size during iteration"); Dewy rejects it at compile time
    with pytest.raises(UserError, match='cannot mutate `s` while iterating it'):
        _check("    let s = set[1 2]\n    loop x in s { s.pop(x); }")
    with pytest.raises(UserError, match='cannot mutate `d` while iterating it'):
        _check("    let d = ['a' -> 1]\n    loop [k v] in d { d['z'] = 2 }")


def test_set_algebra_dispatches_on_set_operands() -> None:
    root = _check("    let a = set[1 2]\n    let b = set[2 3]\n    let u = a | b\n    let i = a and b\n    let d = a - b\n    let x = a xor b")
    body = {item.name: item for item in root.items[0].expr.body.items if isinstance(item, hir.Declare)}
    assert [body[name].expr.op for name in ('u', 'i', 'd', 'x')] == ['union', 'intersection', 'difference', 'symmetric']
    assert all(ty.set_element(body[name].expr.type) == 'int64' for name in ('u', 'i', 'd', 'x'))
    with pytest.raises(TypeCheckError, match='different element types'):
        _check("    let a = set[1 2]\n    let b = set['x']\n    let u = a | b")


def test_dictionary_union_and_views() -> None:
    root = _check("    let a = ['x' -> 1]\n    let b = ['y' -> 2]\n    let u = a | b\n    let ks = a.keys\n    let vs = a.values\n    let s = set[1]\n    let ms = s.values")
    body = {item.name: item for item in root.items[0].expr.body.items if isinstance(item, hir.Declare)}
    assert isinstance(body['u'].expr, hir.SetAlgebra) and ty.dict_key_value(body['u'].expr.type) == ('string', 'int64')
    assert isinstance(body['ks'].expr, hir.DictView) and ty.set_element(body['ks'].expr.type) == 'string'
    assert isinstance(body['vs'].expr, hir.DictView) and body['vs'].expr.type == ty.ArrayType('int64', None)
    assert isinstance(body['ms'].expr, hir.DictView) and body['ms'].expr.type == ty.ArrayType('int64', None)
    with pytest.raises(TypeCheckError, match='no matching overload for operator `&`'):
        _check("    let a = ['x' -> 1]\n    let b = ['y' -> 2]\n    let u = a & b")
    with pytest.raises(UserError, match='sets have no keys'):
        _check("    let s = set[1]\n    let k = s.keys")


def test_compound_store_updates_a_proven_key_in_place() -> None:
    root = _check(
        "    let d = ['a' -> 1]\n"
        "    d['a'] += 1\n"
        "    let k:string = 'b'\n"
        "    if k in? d { d[k] *= 2 }"
    )
    stores = _nodes(root, hir.DictStore)
    assert len(stores) == 2 and all(isinstance(store.value, hir.FunctionCall) for store in stores)
    assert len(_lookups(root)) == 2 and all(lookup.proven for lookup in _lookups(root))


def test_compound_store_needs_a_proven_key() -> None:
    with pytest.raises(UserError, match='dictionary key is not proven present'):
        _check("    let d = ['a' -> 1]\n    let k:string = 'b'\n    d[k] += 1")


@pytest.mark.parametrize('guard', ['key not in? entries', 'not (key in? entries)'])
@pytest.mark.parametrize('key_type', ['string', 'addr'])
def test_negative_membership_return_guard_proves_the_continuing_lookup(guard, key_type):
    root = check.typecheck_and_resolve(SrcFile(None, f'''
f = (key:{key_type} @entries:dict<{key_type} int64>):>int64 => {{
    if {guard} return 0
    let value = entries[key]
    entries[key] = value + 1
    return value
}}
'''))
    assert all(lookup.proven for lookup in _lookups(root))


def test_negated_membership_proof_still_expires_on_mutation():
    with pytest.raises(UserError, match='not proven present'):
        _check("let entries:dict<string int64> = []\nlet key:string = 'a'\n"
               'if key not in? entries return 0\nentries.clear\nlet value = entries[key]')


@pytest.mark.parametrize('declaration', [
    "let p=[entries=['a' -> 1]]",
    "let p:[entries:dict<string int64>]=[entries=['a' -> 1]]",
    "Box:type=const [entries:dict<string int64>]\nlet p=Box[['a' -> 1]]",
])
def test_nested_container_literals_seed_member_routes(declaration):
    root = _check(declaration + "\nlet value=p.entries['a']")
    lookup, = _lookups(root)
    assert lookup.proven and lookup.static_position == 0


def test_replacing_an_enclosing_record_expires_literal_key_proofs():
    for replacement in ("p=[entries=['b' -> 2]]", "p.entries=['b' -> 2]"):
        with pytest.raises(UserError, match='key is not proven present'):
            _check("let p=[entries=['a' -> 1]]\n" + replacement + "\nlet value=p.entries['a']")


def test_unpacked_dictionary_records_are_read_only_borrows():
    with pytest.raises(UserError, match='const object|read.only'):
        _check("let d=['a' -> [x=1]]\nloop [k v] in d {v.x=2}")
    _check("let d=['a' -> [x=1]]\nloop [k v] in d {let own=v own.x=2}")
    with pytest.raises(UserError, match='set iterator has one target'):
        _check('let s=set[1 2]\nloop [k v] in s {}')
