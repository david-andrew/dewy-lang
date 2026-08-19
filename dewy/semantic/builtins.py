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
    'nand': '__nand__',
    'nor': '__nor__',
    'xnor': '__xnor__',
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


def _udewy_intrinsic(
    params: list[ty.TypeExpr],
    ret: ty.TypeExpr,
) -> ty.FunctionType:
    return ty.FunctionType(
        [ty.PosOrKwArg(None, param) for param in params],
        [],
        None,
        ret,
    )


_udewy_word_intrinsic_arities: dict[str, int] = {
    '__i64_to_f32_bits__': 1,
    '__i64_to_f64_bits__': 1,
    '__f32_bits_to_i64__': 1,
    '__f64_bits_to_i64__': 1,
    '__host_log__': 2,
    '__host_exit__': 1,
    '__host_time__': 0,
    '__host_random__': 0,
    '__dom_set_text__': 2,
    '__dom_append__': 2,
    '__dom_clear__': 0,
    '__dom_append_int__': 1,
    '__log_int__': 1,
    '__canvas_init__': 2,
    '__canvas_width__': 0,
    '__canvas_height__': 0,
    '__canvas_present__': 0,
    '__canvas_set_aspect_lock__': 1,
    '__frame_count__': 0,
    '__frame_time__': 0,
    '__window_width__': 0,
    '__window_height__': 0,
    '__pointer_x__': 0,
    '__pointer_y__': 0,
    '__pointer_down__': 0,
    '__pointer_buttons__': 0,
    '__pointer_wheel__': 0,
    '__key_down__': 2,
    '__key_pressed__': 2,
    '__key_released__': 2,
    '__audio_init__': 3,
    '__audio_play__': 0,
    '__audio_sample_rate__': 0,
    '__audio_stream_init__': 2,
    '__audio_stream_write__': 0,
    '__audio_stream_needs_samples__': 0,
    '__webgl_init__': 4,
    '__webgl_uniform1i__': 3,
    '__webgl_uniform2i__': 4,
    '__webgl_uniform1iv__': 4,
    '__webgl_uniform2iv__': 4,
    '__webgl_render__': 0,
    '__gpu_init__': 2,
    '__gpu_set_viewport__': 2,
    '__gpu_clear__': 3,
    '__gpu_set_perspective_frustum__': 6,
    '__gpu_set_view_matrix__': 1,
    '__gpu_set_texture__': 1,
    '__gpu_set_blend__': 1,
    '__gpu_set_depth_test__': 1,
    '__gpu_set_depth_write__': 1,
    '__gpu_set_line_width__': 1,
    '__gpu_submit__': 3,
    '__gpu_overlay_begin__': 2,
    '__gpu_overlay_end__': 0,
    '__gpu_create_texture__': 5,
    '__gpu_present__': 0,
    '__gpu_window_width__': 0,
    '__gpu_window_height__': 0,
    '__audio_queue_init__': 2,
    '__audio_queue_push__': 2,
    '__audio_queue_size__': 0,
}


udewy_intrinsic_types: dict[str, ty.FunctionType] = {
    **{
        f'__load_{prefix}{width}__': _udewy_intrinsic(
            [ty.TOP_TYPE],
            f'{type_prefix}{width}',
        )
        for prefix, type_prefix in (('i', 'int'), ('u', 'uint'))
        for width in (8, 16, 32, 64)
    },
    **{
        f'__store_{prefix}{width}__': _udewy_intrinsic(
            [f'{type_prefix}{width}', ty.TOP_TYPE],
            ty.VOID_TYPE,
        )
        for prefix, type_prefix in (('i', 'int'), ('u', 'uint'))
        for width in (8, 16, 32, 64)
    },
    '__load__': _udewy_intrinsic([ty.TOP_TYPE], 'int64'),
    '__store__': _udewy_intrinsic(['int64', ty.TOP_TYPE], ty.VOID_TYPE),
    '__alloca__': _udewy_intrinsic(['int64'], 'int64'),
    '__static_alloca__': _udewy_intrinsic(['int64'], 'int64'),
    '__signed_shr__': _signed_shift_intrinsic(),
    '__unsigned_idiv__': _udewy_intrinsic(['uint64', 'uint64'], 'uint64'),
    '__unsigned_mod__': _udewy_intrinsic(['uint64', 'uint64'], 'uint64'),
    '__unsigned_lt__': _udewy_intrinsic(['uint64', 'uint64'], 'bool'),
    '__unsigned_gt__': _udewy_intrinsic(['uint64', 'uint64'], 'bool'),
    '__unsigned_lte__': _udewy_intrinsic(['uint64', 'uint64'], 'bool'),
    '__unsigned_gte__': _udewy_intrinsic(['uint64', 'uint64'], 'bool'),
    '__static_words__': ty.FunctionType(
        [ty.PosOrKwArg(None, ty.TOP_TYPE)],
        [],
        'words',
        'int64',
    ),
    **{
        name: _udewy_intrinsic(['int64'] * arity, 'int64')
        for name, arity in _udewy_word_intrinsic_arities.items()
    },
    **{
        f'__syscall{arity}__': _udewy_intrinsic(
            ['int64'] * (arity + 1),
            'int64',
        )
        for arity in range(7)
    },
}


# TODO: dealing with type promotions.
# probably the dispatch system would be able to track promotions that need to happen
builtin_types: dict[str, ty.TypeExpr] = {
    '__add__': ty.OverloadType([
        _binary_generic('number'),
        _binary_concrete(ty.StringType(), ty.StringType()),
    ]),
    '__sub__': _binary_generic('number'),
    '__mul__': _binary_generic('number'),
    '__floordiv__': _binary_generic('int'),
    '__mod__': _binary_generic('int'),
    '__lshift__': _shift_generic(),
    '__rshift__': _shift_generic(),
    '__eq__': _binary_generic(ty.TOP_TYPE, 'bool'),
    '__ne__': _binary_generic(ty.TOP_TYPE, 'bool'),
    '__gt__': _binary_generic('number', 'bool'),
    '__lt__': _binary_generic('number', 'bool'),
    '__ge__': _binary_generic('number', 'bool'),
    '__le__': _binary_generic('number', 'bool'),
    '__and__': _bitwise_overload(callable_overload=True),
    '__or__': _bitwise_overload(),
    '__xor__': _bitwise_overload(),
    '__nand__': _bitwise_overload(),
    '__nor__': _bitwise_overload(),
    '__xnor__': _bitwise_overload(),
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
    **udewy_intrinsic_types,
}

builtin_type_aliases: dict[str, ty.TypeExpr] = {
    # Base physical dimensions are compile-time-only type factors.  The
    # prelude builds representation-parameterized quantities from them.
    'Time': ty.dimension(('Time', 1)),
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
