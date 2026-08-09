"""Tests for TypeFunc subtyping, kwargs matrix, calls, overloads, and dispatch."""

import pytest

from src.cleanparse.semantic.ty import (
    DispatchError,
    KwOnlyArg,
    PosOrKwArg,
    FunctionType,
    OverloadType,
    TypeSystem,
    instantiate_method,
)

TS = TypeSystem()
is_subtype = TS.is_subtype
function_subtype = TS.function_subtype
callable_subtype = TS.callable_subtype
call_accepted = TS.call_accepted
applicable = TS.applicable
more_specific = TS.more_specific


def select(methods: list[FunctionType], pos_types: list[str]) -> FunctionType:
    return TS.match_best_function(methods, pos_types).method


def overload_function(a: FunctionType | OverloadType, b: FunctionType | OverloadType) -> OverloadType:
    def methods(t: FunctionType | OverloadType) -> list[FunctionType]:
        return t.methods if isinstance(t, OverloadType) else [t]
    return OverloadType(methods(a) + methods(b))


def F(
    pos: list[tuple[str, str]] | None = None,
    *,
    kw: list[tuple[str, str, bool]] | None = None,
    rest: str | None = None,
    ret: str = 'any',
) -> FunctionType:
    return FunctionType(
        [PosOrKwArg(n, t) for n, t in (pos or [])],
        [KwOnlyArg(n, t, req) for n, t, req in (kw or [])],
        rest,
        ret,
    )


# ---------------------------------------------------------------------------
# Variance
# ---------------------------------------------------------------------------

def test_contravariant_args_covariant_return():
    # (number)->int  of?  (int)->number
    f = F([('x', 'number')], ret='int')
    g = F([('x', 'int')], ret='number')
    assert function_subtype(f, g)
    assert is_subtype(f, g)
    assert not function_subtype(g, f)


def test_same_function_reflexive():
    f = F([('x', 'int')], ret='int')
    assert function_subtype(f, f)
    assert is_subtype(f, f)


# ---------------------------------------------------------------------------
# Optional / required kwargs matrix
# ---------------------------------------------------------------------------

def test_optional_expected_rejects_required_provided():
    # G expects optional flag; F requires flag — not usable
    g = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    f = F([('x', 'int')], kw=[('flag', 'bool', True)], ret='void')
    assert not function_subtype(f, g)


def test_optional_expected_accepts_optional_provided():
    g = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    f = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    assert function_subtype(f, g)


def test_required_expected_accepts_optional_or_required_provided():
    g = F([('x', 'int')], kw=[('flag', 'bool', True)], ret='void')
    f_opt = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    f_req = F([('x', 'int')], kw=[('flag', 'bool', True)], ret='void')
    assert function_subtype(f_opt, g)
    assert function_subtype(f_req, g)


def test_extra_optional_on_f_ok():
    g = F([('x', 'int')], ret='void')
    f = F([('x', 'int')], kw=[('debug', 'bool', False)], ret='void')
    assert function_subtype(f, g)


def test_extra_required_on_f_not_ok():
    g = F([('x', 'int')], ret='void')
    f = F([('x', 'int')], kw=[('debug', 'bool', True)], ret='void')
    assert not function_subtype(f, g)


def test_missing_optional_kw_without_rest_not_ok():
    # G may pass flag; F has neither flag nor rest
    g = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    f = F([('x', 'int')], ret='void')
    assert not function_subtype(f, g)


def test_rest_accepts_g_optional_kw():
    g = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    f = F([('x', 'int')], rest='rest', ret='void')
    assert function_subtype(f, g)


# ---------------------------------------------------------------------------
# Call acceptance / select (single method)
# ---------------------------------------------------------------------------

def test_call_accepted_positional():
    m = F([('x', 'number'), ('y', 'string')], ret='bool')
    assert call_accepted(m, ['int', 'string'], {})
    assert not call_accepted(m, ['string', 'string'], {})
    assert not call_accepted(m, ['int'], {})


def test_call_accepted_kwargs():
    m = F([('x', 'int')], kw=[('flag', 'bool', False)], ret='void')
    assert call_accepted(m, ['int'], {})
    assert call_accepted(m, ['int'], {'flag': 'bool'})
    assert not call_accepted(m, ['int'], {'flag': 'string'})
    assert not call_accepted(m, ['int'], {'unknown': 'bool'})


def test_call_required_kw():
    m = F([('x', 'int')], kw=[('mode', 'string', True)], ret='void')
    assert not call_accepted(m, ['int'], {})
    assert call_accepted(m, ['int'], {'mode': 'string'})


def test_select_single_method():
    m = F([('x', 'int')], ret='string')
    assert select([m], ['int']) is m
    with pytest.raises(DispatchError):
        select([m], ['string'])


# ---------------------------------------------------------------------------
# Overloads + dispatch
# ---------------------------------------------------------------------------

def test_overload_and_builds_set():
    a = F([('x', 'int')], ret='string')
    b = F([('x', 'string'), ('y', 'string')], ret='string')
    o = overload_function(a, b)
    assert isinstance(o, OverloadType)
    assert len(o.methods) == 2


def test_overload_coverage_subtype():
    a = F([('x', 'int')], ret='void')
    b = F([('x', 'string')], ret='void')
    o = overload_function(a, b)
    assert callable_subtype(o, a)
    assert callable_subtype(o, b)
    assert not callable_subtype(a, o)


def test_dispatch_picks_more_specific():
    wide = F([('x', 'number')], ret='void')
    narrow = F([('x', 'int')], ret='void')
    o = overload_function(wide, narrow)
    chosen = select(o.methods, ['int'])
    assert chosen is narrow


def test_dispatch_ambiguous():
    a = F([('x', 'int'), ('y', 'number')], ret='void')
    b = F([('x', 'number'), ('y', 'int')], ret='void')
    with pytest.raises(DispatchError, match='ambiguous'):
        select([a, b], ['int', 'int'])


def test_dispatch_no_match():
    a = F([('x', 'int')], ret='void')
    with pytest.raises(DispatchError, match='no matching'):
        select([a], ['string'])


def test_more_specific_relation():
    wide = F([('x', 'number')], ret='void')
    narrow = F([('x', 'int')], ret='void')
    assert more_specific(narrow, wide)
    assert not more_specific(wide, narrow)
    assert not more_specific(narrow, narrow)


def test_applicable_filters_kwargs():
    m = F([('x', 'int')], kw=[('flag', 'bool', True)], ret='void')
    assert applicable([m], ['int'], {}) == []
    assert applicable([m], ['int'], {'flag': 'bool'}) == [m]


# ---------------------------------------------------------------------------
# Generics scaffolding
# ---------------------------------------------------------------------------

def test_instantiate_method_noop_without_params():
    m = F([('x', 'int')], ret='int')
    assert instantiate_method(m, {}) is m


def test_instantiate_method_substitutes_params():
    from src.cleanparse.semantic.ty import GenericParam
    m = FunctionType(
        [PosOrKwArg('x', 'T')],
        [],
        None,
        'T',
        [GenericParam('T', 'number')],
    )
    inst = instantiate_method(m, {'T': 'int'})
    assert inst.pos_or_kw[0].type == 'int'
    assert inst.ret == 'int'
    assert inst.type_params == []
