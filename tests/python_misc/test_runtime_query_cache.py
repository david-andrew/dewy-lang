"""Representation caches expire before another program can change type state."""

import pytest

from dewy.backend.udewy import emit, lower
from dewy.reporting import SrcFile
from dewy.semantic import check, ty


def test_callable_abi_reused_without_crossing_compilations():
    source = SrcFile(None, 'main=():>int64=>42')
    checked = check.typecheck_and_resolve(source, include_prelude=False)
    first = lower._Lowerer(checked, source)
    record = ty.ObjectType((ty.ObjectField('text', 'string'),))
    signature = ty.FunctionType(
        [ty.PosOrKwArg('value', record, place=True)],
        [ty.KwOnlyArg('fallback', 'string', required=False)], None, record,
    )
    abi = first._lower_callable_type(signature)
    assert abi.ret == ty.VOID_TYPE
    assert [param.type for param in abi.pos_or_kw] == ['int64', 'int64', 'bool', 'int64']
    assert abi.kw_only == []
    assert first._lower_callable_type(signature) is abi
    assert signature.ret is record and signature.pos_or_kw[0].place

    # Later checking can change descriptions; a new lowerer must not reuse
    # the previous signature or its hidden aggregate return slot.
    signature.ret = 'int64'
    second = lower._Lowerer(checked, source)
    revised = second._lower_callable_type(signature)
    assert revised is not abi and revised.ret == 'int64'
    assert [param.type for param in revised.pos_or_kw] == ['int64', 'int64', 'bool']


def test_bounds_query_scope_expires_before_type_changes(monkeypatch):
    from dewy.semantic.analyze import bounds
    from dewy.semantic import bindings, hir
    from dewy.reporting import Span

    choice = ty.TypeOr(['int64', 'none'])
    observations = []
    original = bounds._BoundsValidator.validate

    def validate(self, root, *, effect_context=None):
        assert ty._runtime_query_cache.get() is not None
        observations.append(ty.optional_payload(choice))
        original(self, root, effect_context=effect_context)

    monkeypatch.setattr(bounds._BoundsValidator, 'validate', validate)
    source = SrcFile(None, '')
    root = hir.Block(Span(0, 0), ty.VOID_TYPE, [], True)
    registry = bindings.BindingRegistry()
    bounds.validate_bounds(root, registry, source)
    assert ty._runtime_query_cache.get() is None
    choice.items.append('bool')
    bounds.validate_bounds(root, registry, source)
    assert observations == ['int64', None]
    assert ty._runtime_query_cache.get() is None


def test_mutable_union_queries_are_live_outside_lowering():
    choice = ty.TypeOr(['int64', 'none'])
    assert ty.optional_payload(choice) == 'int64'
    with ty.runtime_query_scope():
        assert ty.optional_payload(choice) == 'int64'
        assert ty.runtime_union_members(choice) is None
    choice.items.append('bool')
    assert ty.optional_payload(choice) is None
    with ty.runtime_query_scope():
        assert ty.runtime_union_members(choice) == ('none', 'bool', 'int64')


def test_scope_restores_state_after_failure():
    choice = ty.TypeOr(['bool', 'int64'])
    with pytest.raises(RuntimeError):
        with ty.runtime_query_scope():
            assert ty.runtime_union_members(choice) == ('bool', 'int64')
            raise RuntimeError('failed compilation')
    choice.items.append('none')
    assert ty.runtime_union_members(choice) == ('none', 'bool', 'int64')


def test_nested_lowering_uses_same_query_scope():
    choice = ty.TypeOr(['bool', 'int64'])
    with ty.runtime_query_scope():
        members = ty.runtime_union_members(choice)
        with ty.runtime_query_scope():
            assert ty.runtime_union_members(choice) is members
        assert ty.runtime_union_members(choice) is members


def test_cached_and_uncached_emission_agree(monkeypatch):
    source = SrcFile(None, '''
        Choice:type = [text:string code:int64] | bool | none
        let choose=(flag:bool):>Choice=>{
            if flag return [text='hello' code=42]
            return none
        }
        let main=():>int64=>{
            let value=choose(true)
            if value is? [text:string code:int64] return value.code
            return 0
        }
    ''')
    cached = emit.codegen_inner(check.typecheck_and_resolve(source, include_prelude=True), source)
    monkeypatch.setattr(lower, 'lower_for_udewy', lower.lower_for_udewy.__wrapped__)
    uncached = emit.codegen_inner.__wrapped__(check.typecheck_and_resolve(source, include_prelude=True), source)
    assert cached == uncached


def test_brand_numbering_is_once_per_lowering_and_expires_between_programs(monkeypatch):
    original = ty.brand_ids
    snapshots = []

    def counted():
        result = original()
        snapshots.append(result)
        return result

    monkeypatch.setattr(ty, 'brand_ids', counted)
    family = 'Root=type of [value:int64]\n' + '\n'.join(
        f'Child{i}=type of Root & [extra{i}:int64]' for i in range(32))
    predicates = '\n'.join(f'test{i}=(value:Root):>bool=>value is? Child{i}' for i in range(32))
    body = family + '\n' + predicates + '\nmain=():>int64=>{let value:Root=Child0[42 0] return value.value}\n'
    first = SrcFile(None, body)
    checked = check.typecheck_and_resolve(first, include_prelude=True)
    expected = original()
    emit.codegen_inner(checked, first)
    assert snapshots == [expected]
    second = SrcFile(None, 'Separate=type of [x:int64]\n' + body)
    checked = check.typecheck_and_resolve(second, include_prelude=True)
    expected = original()
    emit.codegen_inner(checked, second)
    assert len(snapshots) == 2
    assert snapshots[-1] == expected
    assert snapshots[0] != snapshots[1]


def test_brand_numbering_preserves_preorder_ranges_and_postorder_entries(monkeypatch):
    monkeypatch.setattr(ty, 'USER_BRAND_TYPES', dict.fromkeys(['Root', 'Other', 'Left', 'Right', 'Grand']))
    monkeypatch.setattr(ty, 'USER_BRAND_PARENTS', {'Left': 'Root', 'Right': 'Root', 'Grand': 'Left'})
    assert list(ty.brand_ids().items()) == [
        ('Grand', (3, 4)), ('Left', (2, 4)), ('Right', (4, 5)),
        ('Root', (1, 5)), ('Other', (5, 6)),
    ]


def test_lowering_reuses_its_nominal_graph(monkeypatch):
    source = SrcFile(None, '''
        Base=type of [value:int64]
        CacheChild=type of Base & [label:string]
        Choice:type=Base|none
        read_choice=(choice:Choice):>int64=>{
            if choice is? CacheChild return choice.value
            if choice is? Base return choice.value
            return 0
        }
        main=():>int64=>read_choice(CacheChild[42 'ok'])
    ''')
    checked = check.typecheck_and_resolve(source, include_prelude=True)
    constructed = 0
    original = ty.TypeSystem.__init__

    def counted(self, *args, **kwargs):
        nonlocal constructed
        constructed += 1
        original(self, *args, **kwargs)

    monkeypatch.setattr(ty.TypeSystem, '__init__', counted)
    emitted = emit.codegen_inner(checked, source, debug_locations=False)
    assert emitted
    assert constructed == 1
