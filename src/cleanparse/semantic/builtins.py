from . import ty

# TODO: TBD if this is the place for these
#       perhaps we might have a dedicate operators file which details all the facets of operators
#       there's also a need for the implementations of each of these builtins, or how they map to the generated code


# under the hood, binary ops are just sugar for method calls on system included methods
BINOP_DUNDER_MAP = {
    # binary operators
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    # '/': '__truediv__',
    '//': '__floordiv__',
    # '\\': '__solve__',
    '%': '__mod__',
    # '^': '__pow__',
    # '.': '__access__',
    '=?': '__eq__',
    '>?': '__gt__',
    '<?': '__lt__',
    '>=?': '__ge__',
    '<=?': '__le__',
    'and': '__and__',
    '&': '__and__',
    'or': '__or__',
    '|': '__or__',
    'xor': '__xor__',
    # 'nand': '__nand__',
    # 'nor': '__nor__',
    # 'xnor': '__xnor__',
    '>>': '__rshift__',
    '<<': '__lshift__',
}

INVERTED_COMPARISON_DUNDER_MAP = {
    '=?': '__ne__',
    '>?': '__le__',
    '<?': '__ge__',
    '>=?': '__lt__',
    '<=?': '__gt__',
}

"""
TODO: some special cases
indexing: `x[y]` -> `__index__(x y)`
"""

UNARY_PREFIX_DUNDER_MAP = {
    # unary prefix operators
    '~': '__not__',
    'not': '__not__',
    # '`': '__cycle_left__',
    # '*': '__unary_multiply__',
    # '/': '__unary_divide__',
    # '+': '__unary_add__',
    '-': '__unary_sub__',

}

UNARY_POSTFIX_DUNDER_MAP = {
    # unary postfix operators
    # '`': '__cycle_right__',

}

# TODO: would be much nicer if all of these could just be written out in dewy
#       eventually we will close this loop
"""
__add__ = ( <T of number>(left:T right:T):>T => builtin )
        & ( (left:string right:string):>string => builtin )
        & ( <T>(left:range<T>|multirange<T> right:range<T>|multirange<T>):>multirange<T> => builtin )

__sub__ = ( <T of number>(left:T right:T):>T => builtin )
        & ( (left:string right:string):>string => builtin )
        & ( <T>(left:range<T>|multirange<T> right:range<T>|multirange<T>):>multirange<T> => builtin )

__mul__ = ( <T of number>(left:T right:T):>T => builtin )


# TODO: note actually this isn't quite correct for truediv. 3/4 does not return int even though 3 is? int and 4 is? int is true.
__div__ = ( <T of number>(left:T right:T & ~0):>T => builtin )
        & ( <T of number>(left:T right:T & 0):>error => builtin )

__floordiv__ = ( <T of number>(left:T right:T & ~0):>T => builtin )
             & ( <T of number>(left:T right:T & 0):>error => builtin )


__and__ = ( <T of int>(left:T right:T):>T => builtin )   # bitwise
        & ( (left:bool right:bool):>bool => builtin )    # logical
        & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )
        & ( (left:function|multifunction right:function|multifunction):>multifunction => builtin )

__or__ = ( <T of int>(left:T right:T):>T => builtin )
       & ( (left:bool right:bool):>bool => builtin )
       & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )

__xor__ = ( <T of int>(left:T right:T):>T => builtin )
        & ( (left:bool right:bool):>bool => builtin )
        & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )

__nand__ = ( <T of int>(left:T right:T):>T => builtin )
         & ( (left:bool right:bool):>bool => builtin )
         & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )

__nor__ = ( <T of int>(left:T right:T):>T => builtin )
        & ( (left:bool right:bool):>bool => builtin )
        & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )

__xnor__ = ( <T of int>(left:T right:T):>T => builtin )
         & ( (left:bool right:bool):>bool => builtin )
         & ( (left:iterator|multiiterator right:iterator|multiiterator):>multiiterator => builtin )

"""
def _binary_generic(bound: ty.TypeExpr, ret: ty.TypeExpr = 'T') -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg('left', 'T'), ty.PosOrKwArg('right', 'T')],
        [],
        None,
        ret,
        [ty.GenericParam('T', bound)],
    )


def _binary_concrete(arg: ty.TypeExpr, ret: ty.TypeExpr = 'int') -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg('left', arg), ty.PosOrKwArg('right', arg)],
        [],
        None,
        ret,
        [],
    )


def _bitwise_overload(*, callable_overload: bool = False) -> ty.OverloadType:
    methods = [
        _binary_generic('int'),
        _binary_concrete('bool', 'bool'),
    ]
    if callable_overload:
        methods.append(
            ty.FunctionType(
                [
                    ty.PosOrKwArg('left', ty.TypeOr(['function', 'multifunction'])),
                    ty.PosOrKwArg('right', ty.TypeOr(['function', 'multifunction'])),
                ],
                [],
                None,
                'multifunction',
                [],
            )
        )
    return ty.OverloadType(methods)


def _unary_generic(bound: ty.TypeExpr) -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg('item', 'T')],
        [],
        None,
        'T',
        [ty.GenericParam('T', bound)],
    )


def _shift_generic() -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg('left', 'T'), ty.PosOrKwArg('right', 'int')],
        [],
        None,
        'T',
        [ty.GenericParam('T', 'int')],
    )


def _signed_shift_intrinsic() -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg('left', 'int64'), ty.PosOrKwArg('right', 'int')],
        [],
        None,
        'int64',
    )


# TODO: dealing with type promotions.
# probably the dispatch system would be able to track promotions that need to happen
builtin_types: dict[str, ty.TypeExpr] = {
    '__add__': _binary_generic('number'),
    '__sub__': _binary_generic('number'),
    '__mul__': _binary_generic('number'),
    '__floordiv__': _binary_generic('int'),
    '__mod__': _binary_generic('int'),
    '__lshift__': _shift_generic(),
    '__rshift__': _shift_generic(),
    '__signed_shr__': _signed_shift_intrinsic(),
    '__eq__': _binary_generic(ty.TOP_TYPE, 'bool'),
    '__ne__': _binary_generic(ty.TOP_TYPE, 'bool'),
    '__gt__': _binary_generic('number', 'bool'),
    '__lt__': _binary_generic('number', 'bool'),
    '__ge__': _binary_generic('number', 'bool'),
    '__le__': _binary_generic('number', 'bool'),
    '__and__': _bitwise_overload(callable_overload=True),
    '__or__': _bitwise_overload(),
    '__xor__': _bitwise_overload(),
    '__unary_sub__': _unary_generic('number'),
    '__not__': ty.OverloadType([
        _unary_generic('int'),
        ty.FunctionType(
            [ty.PosOrKwArg('item', 'bool')],
            [],
            None,
            'bool',
            [],
        ),
    ]),
}

# Explicit cross-branch promote rules (a, b, result). Along-edge cases use the subtype graph.
builtin_promote_rules: list[tuple[str, str, str]] = [
    ('int', 'float', 'float'),
    ('int', 'float32', 'float32'),
    ('int', 'float64', 'float64'),
]


def apply_builtin_promote_rules(ts: ty.TypeSystem) -> None:
    for a, b, result in builtin_promote_rules:
        ts.add_promote_rule(a, b, result)
