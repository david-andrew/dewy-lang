"""Tests for generic method instantiation and promote-and-redispatch."""

import pytest

from src.semantic import builtins
from src.semantic.ty import (
    DispatchError,
    OverloadType,
    StringType,
    TypeSystem,
)


def _ts() -> TypeSystem:
    ts = TypeSystem()
    builtins.apply_builtin_promote_rules(ts)
    return ts


def test_add_same_types_no_promotion():
    ts = _ts()
    add = builtins.builtin_types['__add__']
    assert isinstance(add, OverloadType)
    r = ts.match_best_function(add.methods, ['int', 'int'])
    assert r.method.ret == 'int'
    assert r.promote_pos == [None, None]


def test_add_int_float_promotes_left():
    ts = _ts()
    add = builtins.builtin_types['__add__']
    assert isinstance(add, OverloadType)
    r = ts.match_best_function(add.methods, ['int', 'float'])
    assert r.method.ret == 'float'
    assert r.promote_pos == ['float', None]


def test_add_int_string_rejects():
    ts = _ts()
    add = builtins.builtin_types['__add__']
    assert isinstance(add, OverloadType)
    with pytest.raises(DispatchError):
        ts.match_best_function(add.methods, ['int', 'string'])


def test_add_string_overload() -> None:
    ts = _ts()
    add = builtins.builtin_types['__add__']
    assert isinstance(add, OverloadType)
    result = ts.match_best_function(
        add.methods,
        [StringType(), StringType()],
    )
    assert result.method.ret == StringType()


def test_and_overload_bool_vs_int():
    ts = _ts()
    and_t = builtins.builtin_types['__and__']
    assert isinstance(and_t, OverloadType)

    r = ts.match_best_function(and_t.methods, ['bool', 'bool'])
    assert r.method.ret == 'bool'
    assert r.method.type_params == []

    r = ts.match_best_function(and_t.methods, ['int', 'int'])
    assert r.method.ret == 'int'
