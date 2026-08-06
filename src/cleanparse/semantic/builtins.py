from . import ty

# TODO: TBD if this is the place for these
#       perhaps we might have a dedicate operators file which details all the facets of operators
#       there's also a need for the implementations of each of these builtins, or how they map to the generated code


# under the hood, binary ops are just sugar for method calls on system included methods
BINOP_DUNDER_MAP = {
    # binary operators
    '+': '__add__',
    # '-': '__sub__',
    # '*': '__mul__',
    # '/': '__truediv__',
    # '//': '__floordiv__',
    # '\\': '__solve__',
    # '%': '__mod__',
    # '^': '__pow__',
    # '.': '__access__',
    # 'and': '__and__',
    # '&': '__and__',
    # 'or': '__or__',
    # '|': '__or__',
    # 'xor': '__xor__',
    # 'nand': '__nand__',
    # 'nor': '__nor__',
    # 'xnor': '__xnor__',
    # '>>': '__rshift__',
    # '<<': '__lshift__',
}

"""
TODO: some special cases
indexing: `x[y]` -> `__index__(x y)`
"""

UNARY_PREFIX_DUNDER_MAP = {
    # unary prefix operators
    # '~': '__not__',
    # 'not': '__not__',
    # '`': '__cycle_left__',
    # '*': '__unary_multiply__',
    # '/': '__unary_divide__',
    # '+': '__unary_add__',
    # '-': '__unary_sub__',

}

UNARY_POSTFIX_DUNDER_MAP = {
    # unary postfix operators
    # '`': '__cycle_right__',

}


# TODO: dealing with type promotions.
# probably the dispatch system would be able to track promotions that need to happen
builtin_types: dict[str, ty.TypeExpr] = {
    '__add__': ty.FunctionType(
        [ty.PosOrKwArg('left', 'T'), ty.PosOrKwArg('right', 'T')],
        [],
        None,
        'T',
        [ty.GenericParam('T', 'number')]
    ),
    '__and__': ty.OverloadType([
        ty.FunctionType(
            [ty.PosOrKwArg('left', 'T'), ty.PosOrKwArg('right', 'T')],
            [],
            None,
            'T',
            [ty.GenericParam('T', 'int')]
        ),
        ty.FunctionType(
            [ty.PosOrKwArg('left', 'bool'), ty.PosOrKwArg('right', 'bool')],
            [],
            None,
            'bool',
            []
        ),
    ])
}
