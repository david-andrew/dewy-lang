"""Representation caches expire before another program can change type state."""

import pytest

from dewy.backend.udewy import emit, lower
from dewy.reporting import SrcFile
from dewy.semantic import check, ty


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
