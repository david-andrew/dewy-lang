"""String, grapheme, and unicode lowering: literals, views, slicing, conversions, and string iteration.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from ...parser import t0
from ...reporting import Span
from ...semantic import hir, ty
from ...semantic.hir_display import type_to_dewy
from .lowering_shared import (
    ARRAY_BORROWED_STATIC,
    ARRAY_CAPACITY_OFFSET,
    ARRAY_DATA_OFFSET,
    ARRAY_DESCRIPTOR_SIZE,
    ARRAY_FLAGS_OFFSET,
    ARRAY_LENGTH_OFFSET,
    ARRAY_MUTABLE,
    ARRAY_OWNER_OFFSET,
    ARRAY_STRIDE_OFFSET,
    STRING_BOUNDARIES_OFFSET,
    STRING_BYTE_LENGTH_OFFSET,
    STRING_DATA_OFFSET,
    STRING_DESCRIPTOR_SIZE,
    STRING_GRAPHEME_LENGTH_OFFSET,
    STRING_START_OFFSET,
)
from .runtime_unicode import (
    EXTENDED_PICTOGRAPHIC_RECORDS,
    EXTENDED_PICTOGRAPHIC_TABLE,
    GCB_CONTROL,
    GCB_CR,
    GCB_EXTEND,
    GCB_L,
    GCB_LF,
    GCB_LV,
    GCB_LVT,
    GCB_OTHER,
    GCB_PREPEND,
    GCB_REGIONAL_INDICATOR,
    GCB_SPACING_MARK,
    GCB_T,
    GCB_V,
    GCB_ZWJ,
    GRAPHEME_BREAK_RECORDS,
    GRAPHEME_BREAK_TABLE,
    INCB_CONSONANT,
    INCB_EXTEND,
    INCB_LINKER,
    INCB_NONE,
    INDIC_CONJUNCT_BREAK_RECORDS,
    INDIC_CONJUNCT_BREAK_TABLE,
    TABLE_BYTE_OFFSET,
    TABLE_RECORD_BYTES,
)


class _StringLowering:
    def _extract_string_literal(
        self,
        node: hir.String,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        from ...semantic.unicode.graphemes import grapheme_boundary_byte_offsets

        boundaries = grapheme_boundary_byte_offsets(node.content)
        grapheme_length = len(boundaries) - 1
        allocator = '__static_alloca__'
        boundary_name = self._new_string_temp(
            node.loc,
            'int64',
            'boundaries',
        ).name
        boundaries_pointer = hir.ExpressedIdentifier(
            node.loc,
            'int64',
            boundary_name,
        )
        target = self._new_string_temp(node.loc, node.type)
        statements: list[hir.AST] = [
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                boundary_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [
                        self._int64_literal(
                            node.loc,
                            max(4, len(boundaries) * 4),
                        )
                    ],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(node.loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
        ]
        for index, offset in enumerate(boundaries):
            address = (
                boundaries_pointer
                if index == 0
                else self._int64_binary(
                    '__add__',
                    boundaries_pointer,
                    self._int64_literal(node.loc, index * 4),
                    node.loc,
                )
            )
            statements.append(
                self._intrinsic_call(
                    '__store_u32__',
                    [hir.Integer(node.loc, 'uint32', t0.base10, offset), address],
                    ty.VOID_TYPE,
                    node.loc,
                )
            )
        descriptor = replace(target, type='int64')
        raw_data = replace(node, type='int64')
        statements.extend(
            [
                self._store_i64_field(
                    descriptor,
                    STRING_DATA_OFFSET,
                    raw_data,
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    STRING_BYTE_LENGTH_OFFSET,
                    self._int64_literal(node.loc, len(node.content.encode('utf-8'))),
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    STRING_BOUNDARIES_OFFSET,
                    boundaries_pointer,
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    STRING_GRAPHEME_LENGTH_OFFSET,
                    self._int64_literal(node.loc, grapheme_length),
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    STRING_START_OFFSET,
                    self._int64_literal(node.loc, 0),
                    node.loc,
                ),
            ]
        )
        return statements, target

    def _string_data_start(self, string: hir.AST, loc: Span) -> hir.AST:
        return self._int64_binary(
            '__add__',
            self._load_i64_field(string, STRING_DATA_OFFSET, loc),
            self._load_i64_field(string, STRING_START_OFFSET, loc),
            loc,
        )

    def _extract_representation_cast(
        self,
        node: hir.RepresentationCast,
    ) -> tuple[list[hir.AST], hir.AST]:
        target = node.type
        source = node.expr
        if isinstance(target, ty.ArrayType):
            if target.element == 'uint8':
                if isinstance(source, hir.String) and isinstance(
                    source.type,
                    ty.StringLiteralType,
                ):
                    return self._extract_static_byte_literal_array(node, source)
                if isinstance(source.type, ty.BinaryLiteralType):
                    return self._extract_static_byte_literal_array(node, source)
                prelude, string = self._extract_expression(source)
                descriptor = self._new_array_temp(
                    hir.ArrayLiteral(node.loc, target, [])
                )
                allocation = self._intrinsic_call(
                    '__static_alloca__'
                    if self.lowering_module_startup
                    else '__alloca__',
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                )
                result: list[hir.AST] = [
                    *prelude,
                    hir.Declare(
                        node.loc,
                        ty.VOID_TYPE,
                        'let',
                        descriptor.name,
                        'int64',
                        allocation,
                    ),
                ]
                byte_length = self._load_i64_field(
                    string,
                    STRING_BYTE_LENGTH_OFFSET,
                    node.loc,
                )
                result.extend(
                    [
                        self._store_i64_field(
                            descriptor,
                            ARRAY_DATA_OFFSET,
                            self._string_data_start(string, node.loc),
                            node.loc,
                        ),
                        self._store_i64_field(
                            descriptor,
                            ARRAY_LENGTH_OFFSET,
                            byte_length,
                            node.loc,
                        ),
                        self._store_i64_field(
                            descriptor,
                            ARRAY_CAPACITY_OFFSET,
                            byte_length,
                            node.loc,
                        ),
                        self._store_i64_field(
                            descriptor,
                            ARRAY_STRIDE_OFFSET,
                            self._int64_literal(node.loc, 1),
                            node.loc,
                        ),
                        self._store_i64_field(
                            descriptor,
                            ARRAY_FLAGS_OFFSET,
                            self._int64_literal(node.loc, ARRAY_BORROWED_STATIC),
                            node.loc,
                        ),
                        self._store_i64_field(
                            descriptor,
                            ARRAY_OWNER_OFFSET,
                            replace(string, type='int64'),
                            node.loc,
                        ),
                    ]
                )
                return result, descriptor
            if target.element == 'uint32':
                if isinstance(source.type, ty.StringLiteralType):
                    content = source.type.value
                    items = [
                        hir.Integer(source.loc, 'uint32', t0.base10, ord(character))
                        for character in content
                    ]
                    return self._extract_array_literal(
                        hir.ArrayLiteral(
                            node.loc,
                            ty.ArrayType('uint32', len(items)),
                            items,
                        )
                    )
                return self._string_to_uint32_array(node, source)
            if target.element in {'grapheme', 'char'} and isinstance(
                source.type,
                ty.StringLiteralType,
            ):
                from ...semantic.unicode.graphemes import graphemes

                items = [
                    hir.String(
                        source.loc,
                        ty.StringLiteralType(grapheme),
                        grapheme,
                    )
                    for grapheme in graphemes(source.type.value)
                ]
                return self._extract_array_literal(
                    hir.ArrayLiteral(
                        node.loc,
                        ty.ArrayType(ty.StringType(1), len(items)),
                        items,
                    )
                )
            if target.element in {'grapheme', 'char'}:
                return self._string_to_grapheme_array(node, source)
            self._target_error(
                node,
                f'conversion to `{type_to_dewy(target)}` from a runtime string',
            )
        if (
            isinstance(target, (ty.StringType, ty.StringLiteralType))
            or isinstance(target, str)
            and target in {'string', 'grapheme', 'char'}
        ):
            if (
                isinstance(source.type, ty.ArrayType)
                and (
                    source.type.element in {'grapheme', 'char'}
                    or isinstance(source.type.element, ty.StringType)
                    and source.type.element.length == 1
                )
            ):
                content = self._compile_time_grapheme_array_content(source)
                if content is not None:
                    return self._extract_string_literal(
                        hir.String(
                            node.loc,
                            ty.StringLiteralType(content),
                            content,
                        )
                    )
                return self._grapheme_array_to_string(node, source)
            return self._extract_expression(source)
        self._target_error(node, f'representation conversion to `{type_to_dewy(target)}`')

    def _extract_static_byte_literal_array(
        self,
        node: hir.RepresentationCast,
        source: hir.AST,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if isinstance(source.type, ty.BinaryLiteralType):
            byte_length = len(source.type.value)
            source_prelude, raw_data = self._extract_expression(source)
        else:
            assert isinstance(source, hir.String)
            byte_length = len(source.content.encode('utf-8'))
            source_prelude = []
            raw_data = replace(source, type='int64')
        descriptor = self._new_array_temp(
            hir.ArrayLiteral(node.loc, node.type, [])
        )
        descriptor_word = replace(descriptor, type='int64')
        allocator = (
            '__static_alloca__'
            if self.lowering_module_startup
            else '__alloca__'
        )
        return [
            *source_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_DATA_OFFSET,
                raw_data,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_LENGTH_OFFSET,
                self._int64_literal(node.loc, byte_length),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_CAPACITY_OFFSET,
                self._int64_literal(node.loc, byte_length),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(node.loc, 1),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(node.loc, ARRAY_BORROWED_STATIC),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_OWNER_OFFSET,
                self._int64_literal(node.loc, 0),
                node.loc,
            ),
        ], descriptor

    def _compile_time_grapheme_array_content(
        self,
        node: hir.AST,
    ) -> str | None:
        while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            node = node.expr
        if isinstance(node, hir.ArrayLiteral):
            parts: list[str] = []
            for item in node.items:
                while isinstance(item, (hir.ValueCast, hir.RepresentationCast)):
                    item = item.expr
                if isinstance(item, hir.String):
                    parts.append(item.content)
                elif isinstance(item.type, ty.StringLiteralType):
                    parts.append(item.type.value)
                else:
                    return None
            return ''.join(parts)
        return None

    def _runtime_unicode_property(
        self,
        scalar: hir.AST,
        table: str,
        record_count: int,
        default: int,
        role: str,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        lower_name = self._new_string_temp(loc, 'int64', f'{role}_lower').name
        upper_name = self._new_string_temp(loc, 'int64', f'{role}_upper').name
        middle_name = self._new_string_temp(loc, 'int64', f'{role}_middle').name
        result_name = self._new_string_temp(loc, 'int64', role).name
        lower = hir.ExpressedIdentifier(loc, 'int64', lower_name)
        upper = hir.ExpressedIdentifier(loc, 'int64', upper_name)
        middle = hir.ExpressedIdentifier(loc, 'int64', middle_name)
        result = hir.ExpressedIdentifier(loc, 'int64', result_name)
        record = self._int64_binary(
            '__add__',
            hir.String(loc, 'int64', table),
            self._int64_binary(
                '__mul__',
                middle,
                self._int64_literal(loc, TABLE_RECORD_BYTES),
                loc,
            ),
            loc,
        )

        def decoded_scalar(offset: int) -> hir.AST:
            value: hir.AST = self._int64_literal(loc, 0)
            for byte_offset, shift in zip(range(offset, offset + 4), (18, 12, 6, 0)):
                address = (
                    record
                    if byte_offset == 0
                    else self._int64_binary(
                        '__add__',
                        record,
                        self._int64_literal(loc, byte_offset),
                        loc,
                    )
                )
                byte = replace(
                    self._intrinsic_call('__load_u8__', [address], 'uint8', loc),
                    type='int64',
                )
                digit = self._int64_binary(
                    '__sub__',
                    byte,
                    self._int64_literal(loc, TABLE_BYTE_OFFSET),
                    loc,
                )
                if shift:
                    digit = self._int64_binary(
                        '__lshift__',
                        digit,
                        self._int64_literal(loc, shift),
                        loc,
                    )
                value = self._int64_binary('__add__', value, digit, loc)
            return value

        start = decoded_scalar(0)
        end = decoded_scalar(4)
        property_address = self._int64_binary(
            '__add__',
            record,
            self._int64_literal(loc, 8),
            loc,
        )
        property_value = self._int64_binary(
            '__sub__',
            replace(
                self._intrinsic_call(
                    '__load_u8__',
                    [property_address],
                    'uint8',
                    loc,
                ),
                type='int64',
            ),
            self._int64_literal(loc, TABLE_BYTE_OFFSET),
            loc,
        )
        found = hir.Block(
            loc,
            ty.VOID_TYPE,
            [
                hir.Assign(loc, ty.VOID_TYPE, result, '=', property_value),
                hir.Assign(loc, ty.VOID_TYPE, lower, '=', upper),
            ],
            True,
        )
        search_right = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', end, scalar, loc),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        lower,
                        '=',
                        self._int64_binary(
                            '__add__',
                            middle,
                            self._int64_literal(loc, 1),
                            loc,
                        ),
                    ),
                )
            ],
            found,
        )
        search = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', scalar, start, loc),
                    hir.Assign(loc, ty.VOID_TYPE, upper, '=', middle),
                )
            ],
            search_right,
        )
        loop = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', lower, upper, loc),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                middle,
                                '=',
                                self._int64_binary(
                                    '__rshift__',
                                    self._int64_binary('__add__', lower, upper, loc),
                                    self._int64_literal(loc, 1),
                                    loc,
                                ),
                            ),
                            search,
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        return [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                lower_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                upper_name,
                'int64',
                self._int64_literal(loc, record_count),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                middle_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                result_name,
                'int64',
                self._int64_literal(loc, default),
            ),
            loop,
        ], result

    def _grapheme_array_to_string(
        self,
        node: hir.RepresentationCast,
        source: hir.AST,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        prelude, array = self._extract_expression(source)
        if not isinstance(source.type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: grapheme conversion source is not an array')
        element_type = source.type.element
        loc = node.loc

        element_index_name = self._new_array_name('string_element')
        byte_index_name = self._new_array_name('string_byte')
        byte_length_name = self._new_string_temp(loc, 'int64', 'byte_length').name
        data_name = self._new_string_temp(loc, 'int64', 'data').name
        boundaries_name = self._new_string_temp(loc, 'int64', 'boundaries').name
        descriptor = self._new_string_temp(loc, node.type)
        element_index = hir.ExpressedIdentifier(loc, 'int64', element_index_name)
        byte_index = hir.ExpressedIdentifier(loc, 'int64', byte_index_name)
        byte_length = hir.ExpressedIdentifier(loc, 'int64', byte_length_name)
        data = hir.ExpressedIdentifier(loc, 'int64', data_name)
        boundaries = hir.ExpressedIdentifier(loc, 'int64', boundaries_name)
        array_length = self._load_i64_field(array, ARRAY_LENGTH_OFFSET, loc)

        def current_element() -> hir.AST:
            address = self._array_element_address(
                replace(array, type='int64'),
                element_index,
                element_type,
                loc,
            )
            return self._array_load(address, element_type, loc)

        sum_loop = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', element_index, array_length, loc),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                byte_length,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    byte_length,
                                    self._load_i64_field(
                                        current_element(),
                                        STRING_BYTE_LENGTH_OFFSET,
                                        loc,
                                    ),
                                    loc,
                                ),
                            ),
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                element_index,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    element_index,
                                    self._int64_literal(loc, 1),
                                    loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )

        element_byte_length = self._load_i64_field(
            current_element(),
            STRING_BYTE_LENGTH_OFFSET,
            loc,
        )
        source_byte = self._intrinsic_call(
            '__load_u8__',
            [
                self._int64_binary(
                    '__add__',
                    self._string_data_start(current_element(), loc),
                    byte_index,
                    loc,
                )
            ],
            'uint8',
            loc,
        )
        copy_loop = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        element_index,
                        array_length,
                        loc,
                    ),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                byte_index,
                                '=',
                                self._int64_literal(loc, 0),
                            ),
                            hir.Flow(
                                loc,
                                ty.VOID_TYPE,
                                [
                                    hir.LoopArm(
                                        loc,
                                        ty.VOID_TYPE,
                                        self._int64_comparison(
                                            '__lt__',
                                            byte_index,
                                            element_byte_length,
                                            loc,
                                        ),
                                        hir.Block(
                                            loc,
                                            ty.VOID_TYPE,
                                            [
                                                self._intrinsic_call(
                                                    '__store_u8__',
                                                    [
                                                        source_byte,
                                                        self._int64_binary(
                                                            '__add__',
                                                            data,
                                                            self._int64_binary(
                                                                '__add__',
                                                                self._load_i64_field(
                                                                    descriptor,
                                                                    STRING_BYTE_LENGTH_OFFSET,
                                                                    loc,
                                                                ),
                                                                byte_index,
                                                                loc,
                                                            ),
                                                            loc,
                                                        ),
                                                    ],
                                                    ty.VOID_TYPE,
                                                    loc,
                                                ),
                                                hir.Assign(
                                                    loc,
                                                    ty.VOID_TYPE,
                                                    byte_index,
                                                    '=',
                                                    self._int64_binary(
                                                        '__add__',
                                                        byte_index,
                                                        self._int64_literal(loc, 1),
                                                        loc,
                                                    ),
                                                ),
                                            ],
                                            True,
                                        ),
                                    )
                                ],
                                None,
                            ),
                            self._store_i64_field(
                                descriptor,
                                STRING_BYTE_LENGTH_OFFSET,
                                self._int64_binary(
                                    '__add__',
                                    self._load_i64_field(
                                        descriptor,
                                        STRING_BYTE_LENGTH_OFFSET,
                                        loc,
                                    ),
                                    element_byte_length,
                                    loc,
                                ),
                                loc,
                            ),
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                element_index,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    element_index,
                                    self._int64_literal(loc, 1),
                                    loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )

        utf8_index_name = self._new_string_temp(loc, 'int64', 'utf8_index').name
        scalar_start_name = self._new_string_temp(loc, 'int64', 'scalar_start').name
        scalar_name = self._new_string_temp(loc, 'int64', 'scalar').name
        grapheme_count_name = self._new_string_temp(loc, 'int64', 'grapheme_count').name
        previous_gcb_name = self._new_string_temp(loc, 'int64', 'previous_gcb').name
        ri_count_name = self._new_string_temp(loc, 'int64', 'ri_count').name
        ep_run_name = self._new_string_temp(loc, 'int64', 'ep_run').name
        zwj_ep_name = self._new_string_temp(loc, 'int64', 'zwj_ep').name
        indic_state_name = self._new_string_temp(loc, 'int64', 'indic_state').name
        has_break_name = self._new_string_temp(loc, 'bool', 'has_break').name
        utf8_index = hir.ExpressedIdentifier(loc, 'int64', utf8_index_name)
        scalar_start = hir.ExpressedIdentifier(loc, 'int64', scalar_start_name)
        scalar = hir.ExpressedIdentifier(loc, 'int64', scalar_name)
        grapheme_count = hir.ExpressedIdentifier(loc, 'int64', grapheme_count_name)
        previous_gcb = hir.ExpressedIdentifier(loc, 'int64', previous_gcb_name)
        ri_count = hir.ExpressedIdentifier(loc, 'int64', ri_count_name)
        ep_run = hir.ExpressedIdentifier(loc, 'int64', ep_run_name)
        zwj_ep = hir.ExpressedIdentifier(loc, 'int64', zwj_ep_name)
        indic_state = hir.ExpressedIdentifier(loc, 'int64', indic_state_name)
        has_break = hir.ExpressedIdentifier(loc, 'bool', has_break_name)

        def byte_at(delta: int) -> hir.AST:
            index = (
                utf8_index
                if delta == 0
                else self._int64_binary(
                    '__add__',
                    utf8_index,
                    self._int64_literal(loc, delta),
                    loc,
                )
            )
            return replace(
                self._intrinsic_call(
                    '__load_u8__',
                    [self._int64_binary('__add__', data, index, loc)],
                    'uint8',
                    loc,
                ),
                type='int64',
            )

        def masked_shift(value: hir.AST, mask: int, shift: int) -> hir.AST:
            masked = self._int64_binary(
                '__and__',
                value,
                self._int64_literal(loc, mask),
                loc,
            )
            if shift == 0:
                return masked
            return self._int64_binary(
                '__lshift__',
                masked,
                self._int64_literal(loc, shift),
                loc,
            )

        def decoded(width: int, lead_mask: int) -> hir.AST:
            value = masked_shift(byte_at(0), lead_mask, 6 * (width - 1))
            for delta in range(1, width):
                value = self._int64_binary(
                    '__add__',
                    value,
                    masked_shift(
                        byte_at(delta),
                        0x3F,
                        6 * (width - delta - 1),
                    ),
                    loc,
                )
            return value

        def decode_arm(limit: int | None, width: int, lead_mask: int) -> hir.IfArm:
            condition = (
                hir.Bool(loc, 'bool', True)
                if limit is None
                else self._int64_comparison(
                    '__lt__',
                    byte_at(0),
                    self._int64_literal(loc, limit),
                    loc,
                )
            )
            return hir.IfArm(
                loc,
                ty.VOID_TYPE,
                condition,
                hir.Block(
                    loc,
                    ty.VOID_TYPE,
                    [
                        hir.Assign(
                            loc,
                            ty.VOID_TYPE,
                            scalar,
                            '=',
                            decoded(width, lead_mask),
                        ),
                        hir.Assign(
                            loc,
                            ty.VOID_TYPE,
                            utf8_index,
                            '=',
                            self._int64_binary(
                                '__add__',
                                utf8_index,
                                self._int64_literal(loc, width),
                                loc,
                            ),
                        ),
                    ],
                    True,
                ),
            )

        decode = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                decode_arm(0x80, 1, 0x7F),
                decode_arm(0xE0, 2, 0x1F),
                decode_arm(0xF0, 3, 0x0F),
                decode_arm(None, 4, 0x07),
            ],
            None,
        )
        gcb_prelude, current_gcb = self._runtime_unicode_property(
            scalar,
            GRAPHEME_BREAK_TABLE,
            GRAPHEME_BREAK_RECORDS,
            GCB_OTHER,
            'gcb',
            loc,
        )
        ep_prelude, current_ep = self._runtime_unicode_property(
            scalar,
            EXTENDED_PICTOGRAPHIC_TABLE,
            EXTENDED_PICTOGRAPHIC_RECORDS,
            0,
            'ep',
            loc,
        )
        incb_prelude, current_incb = self._runtime_unicode_property(
            scalar,
            INDIC_CONJUNCT_BREAK_TABLE,
            INDIC_CONJUNCT_BREAK_RECORDS,
            INCB_NONE,
            'incb',
            loc,
        )

        def equal(value: hir.AST, expected: int) -> hir.AST:
            return self._typed_equality(
                value,
                self._int64_literal(loc, expected),
                'int64',
                loc,
            )

        def combine(op: Literal['and', 'or'], conditions: list[hir.AST]) -> hir.AST:
            result = conditions[0]
            for condition in conditions[1:]:
                result = hir.ShortCircuit(loc, 'bool', op, result, condition)
            return result

        def any_equal(value: hir.AST, expected: set[int]) -> hir.AST:
            return combine('or', [equal(value, item) for item in sorted(expected)])

        left_control = any_equal(previous_gcb, {GCB_CR, GCB_LF, GCB_CONTROL})
        right_control = any_equal(current_gcb, {GCB_CR, GCB_LF, GCB_CONTROL})
        break_rules = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [equal(previous_gcb, GCB_CR), equal(current_gcb, GCB_LF)],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine('or', [left_control, right_control]),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', True),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            equal(previous_gcb, GCB_L),
                            any_equal(current_gcb, {GCB_L, GCB_V, GCB_LV, GCB_LVT}),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            any_equal(previous_gcb, {GCB_LV, GCB_V}),
                            any_equal(current_gcb, {GCB_V, GCB_T}),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            any_equal(previous_gcb, {GCB_LVT, GCB_T}),
                            equal(current_gcb, GCB_T),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    any_equal(current_gcb, {GCB_EXTEND, GCB_ZWJ}),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_gcb, GCB_SPACING_MARK),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(previous_gcb, GCB_PREPEND),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            equal(current_incb, INCB_CONSONANT),
                            equal(indic_state, 2),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            equal(current_ep, 1),
                            equal(previous_gcb, GCB_ZWJ),
                            equal(zwj_ep, 1),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    combine(
                        'and',
                        [
                            equal(previous_gcb, GCB_REGIONAL_INDICATOR),
                            equal(current_gcb, GCB_REGIONAL_INDICATOR),
                            equal(ri_count, 1),
                        ],
                    ),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        has_break,
                        '=',
                        hir.Bool(loc, 'bool', False),
                    ),
                ),
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                has_break,
                '=',
                hir.Bool(loc, 'bool', True),
            ),
        )
        boundary_address = self._int64_binary(
            '__add__',
            boundaries,
            self._int64_binary(
                '__mul__',
                grapheme_count,
                self._int64_literal(loc, 4),
                loc,
            ),
            loc,
        )
        add_boundary = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    has_break,
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            self._intrinsic_call(
                                '__store_u32__',
                                [replace(scalar_start, type='uint32'), boundary_address],
                                ty.VOID_TYPE,
                                loc,
                            ),
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                grapheme_count,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    grapheme_count,
                                    self._int64_literal(loc, 1),
                                    loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        segment = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(grapheme_count, 0),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        grapheme_count,
                        '=',
                        self._int64_literal(loc, 1),
                    ),
                )
            ],
            hir.Block(loc, ty.VOID_TYPE, [break_rules, add_boundary], True),
        )
        update_ri = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_gcb, GCB_REGIONAL_INDICATOR),
                    hir.Flow(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.IfArm(
                                loc,
                                ty.VOID_TYPE,
                                equal(previous_gcb, GCB_REGIONAL_INDICATOR),
                                hir.Flow(
                                    loc,
                                    ty.VOID_TYPE,
                                    [
                                        hir.IfArm(
                                            loc,
                                            ty.VOID_TYPE,
                                            equal(ri_count, 1),
                                            hir.Assign(
                                                loc,
                                                ty.VOID_TYPE,
                                                ri_count,
                                                '=',
                                                self._int64_literal(loc, 0),
                                            ),
                                        )
                                    ],
                                    hir.Assign(
                                        loc,
                                        ty.VOID_TYPE,
                                        ri_count,
                                        '=',
                                        self._int64_literal(loc, 1),
                                    ),
                                ),
                            )
                        ],
                        hir.Assign(
                            loc,
                            ty.VOID_TYPE,
                            ri_count,
                            '=',
                            self._int64_literal(loc, 1),
                        ),
                    ),
                )
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                ri_count,
                '=',
                self._int64_literal(loc, 0),
            ),
        )
        update_zwj_ep = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_gcb, GCB_ZWJ),
                    hir.Assign(loc, ty.VOID_TYPE, zwj_ep, '=', ep_run),
                )
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                zwj_ep,
                '=',
                self._int64_literal(loc, 0),
            ),
        )
        update_ep_run = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_ep, 1),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        ep_run,
                        '=',
                        self._int64_literal(loc, 1),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_gcb, GCB_EXTEND),
                    hir.Assign(loc, ty.VOID_TYPE, ep_run, '=', ep_run),
                ),
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                ep_run,
                '=',
                self._int64_literal(loc, 0),
            ),
        )
        update_indic = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_incb, INCB_CONSONANT),
                    hir.Assign(
                        loc,
                        ty.VOID_TYPE,
                        indic_state,
                        '=',
                        self._int64_literal(loc, 1),
                    ),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_incb, INCB_EXTEND),
                    hir.Assign(loc, ty.VOID_TYPE, indic_state, '=', indic_state),
                ),
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    equal(current_incb, INCB_LINKER),
                    hir.Flow(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.IfArm(
                                loc,
                                ty.VOID_TYPE,
                                any_equal(indic_state, {1, 2}),
                                hir.Assign(
                                    loc,
                                    ty.VOID_TYPE,
                                    indic_state,
                                    '=',
                                    self._int64_literal(loc, 2),
                                ),
                            )
                        ],
                        hir.Assign(
                            loc,
                            ty.VOID_TYPE,
                            indic_state,
                            '=',
                            self._int64_literal(loc, 0),
                        ),
                    ),
                ),
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                indic_state,
                '=',
                self._int64_literal(loc, 0),
            ),
        )
        scan_loop = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', utf8_index, byte_length, loc),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                scalar_start,
                                '=',
                                utf8_index,
                            ),
                            decode,
                            *gcb_prelude,
                            *ep_prelude,
                            *incb_prelude,
                            segment,
                            update_ri,
                            update_zwj_ep,
                            update_ep_run,
                            update_indic,
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                previous_gcb,
                                '=',
                                current_gcb,
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        final_boundary = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        self._int64_literal(loc, 0),
                        byte_length,
                        loc,
                    ),
                    self._intrinsic_call(
                        '__store_u32__',
                        [
                            replace(byte_length, type='uint32'),
                            self._int64_binary(
                                '__add__',
                                boundaries,
                                self._int64_binary(
                                    '__mul__',
                                    grapheme_count,
                                    self._int64_literal(loc, 4),
                                    loc,
                                ),
                                loc,
                            ),
                        ],
                        ty.VOID_TYPE,
                        loc,
                    ),
                )
            ],
            None,
        )
        descriptor_word = replace(descriptor, type='int64')
        declarations = [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                element_index_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                byte_index_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                byte_length_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            sum_loop,
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [
                        self._int64_binary(
                            '__add__',
                            byte_length,
                            self._int64_literal(loc, 1),
                            loc,
                        )
                    ],
                    'int64',
                    loc,
                ),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                boundaries_name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [
                        self._int64_binary(
                            '__mul__',
                            self._int64_binary(
                                '__add__',
                                byte_length,
                                self._int64_literal(loc, 1),
                                loc,
                            ),
                            self._int64_literal(loc, 4),
                            loc,
                        )
                    ],
                    'int64',
                    loc,
                ),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    loc,
                ),
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_BYTE_LENGTH_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                element_index,
                '=',
                self._int64_literal(loc, 0),
            ),
            copy_loop,
            self._intrinsic_call(
                '__store_u32__',
                [hir.Integer(loc, 'uint32', t0.base10, 0), boundaries],
                ty.VOID_TYPE,
                loc,
            ),
        ]
        state_declarations = [
            (utf8_index_name, 'int64', self._int64_literal(loc, 0)),
            (scalar_start_name, 'int64', self._int64_literal(loc, 0)),
            (scalar_name, 'int64', self._int64_literal(loc, 0)),
            (grapheme_count_name, 'int64', self._int64_literal(loc, 0)),
            (previous_gcb_name, 'int64', self._int64_literal(loc, GCB_OTHER)),
            (ri_count_name, 'int64', self._int64_literal(loc, 0)),
            (ep_run_name, 'int64', self._int64_literal(loc, 0)),
            (zwj_ep_name, 'int64', self._int64_literal(loc, 0)),
            (indic_state_name, 'int64', self._int64_literal(loc, 0)),
            (has_break_name, 'bool', hir.Bool(loc, 'bool', True)),
        ]
        return [
            *prelude,
            *declarations,
            *[
                hir.Declare(loc, ty.VOID_TYPE, 'let', name, type_, value)
                for name, type_, value in state_declarations
            ],
            scan_loop,
            final_boundary,
            self._store_i64_field(
                descriptor_word,
                STRING_DATA_OFFSET,
                data,
                loc,
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_BYTE_LENGTH_OFFSET,
                byte_length,
                loc,
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_BOUNDARIES_OFFSET,
                boundaries,
                loc,
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_GRAPHEME_LENGTH_OFFSET,
                grapheme_count,
                loc,
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_START_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
        ], descriptor

    def _string_to_uint32_array(
        self,
        node: hir.RepresentationCast,
        source: hir.AST,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        prelude, string = self._extract_expression(source)
        byte_length = self._load_i64_field(
            string,
            STRING_BYTE_LENGTH_OFFSET,
            node.loc,
        )
        input_data = self._string_data_start(string, node.loc)
        descriptor = self._new_array_temp(hir.ArrayLiteral(node.loc, node.type, []))
        data_name = self._new_array_name('codepoints')
        input_index_name = self._new_array_name('utf8_index')
        output_index_name = self._new_array_name('scalar_index')
        scalar_name = self._new_array_name('scalar')
        data = hir.ExpressedIdentifier(node.loc, 'int64', data_name)
        input_index = hir.ExpressedIdentifier(node.loc, 'int64', input_index_name)
        output_index = hir.ExpressedIdentifier(node.loc, 'int64', output_index_name)
        scalar = hir.ExpressedIdentifier(node.loc, 'int64', scalar_name)

        def byte_at(delta: int) -> hir.AST:
            index = (
                input_index
                if delta == 0
                else self._int64_binary(
                    '__add__',
                    input_index,
                    self._int64_literal(node.loc, delta),
                    node.loc,
                )
            )
            loaded = self._intrinsic_call(
                '__load_u8__',
                [self._int64_binary('__add__', input_data, index, node.loc)],
                'uint8',
                node.loc,
            )
            return replace(loaded, type='int64')

        def masked_shift(value: hir.AST, mask: int, shift: int) -> hir.AST:
            masked = self._int64_binary(
                '__and__',
                value,
                self._int64_literal(node.loc, mask),
                node.loc,
            )
            return (
                masked
                if shift == 0
                else self._int64_binary(
                    '__lshift__',
                    masked,
                    self._int64_literal(node.loc, shift),
                    node.loc,
                )
            )

        def decoded(width: int, lead_mask: int) -> hir.AST:
            value = masked_shift(byte_at(0), lead_mask, 6 * (width - 1))
            for delta in range(1, width):
                value = self._int64_binary(
                    '__add__',
                    value,
                    masked_shift(
                        byte_at(delta),
                        0x3F,
                        6 * (width - delta - 1),
                    ),
                    node.loc,
                )
            return value

        def decode_arm(limit: int | None, width: int, lead_mask: int) -> hir.IfArm:
            condition = (
                hir.Bool(node.loc, 'bool', True)
                if limit is None
                else self._int64_comparison(
                    '__lt__',
                    byte_at(0),
                    self._int64_literal(node.loc, limit),
                    node.loc,
                )
            )
            return hir.IfArm(
                node.loc,
                ty.VOID_TYPE,
                condition,
                hir.Block(
                    node.loc,
                    ty.VOID_TYPE,
                    [
                        hir.Assign(
                            node.loc,
                            ty.VOID_TYPE,
                            scalar,
                            '=',
                            decoded(width, lead_mask),
                        ),
                        hir.Assign(
                            node.loc,
                            ty.VOID_TYPE,
                            input_index,
                            '=',
                            self._int64_binary(
                                '__add__',
                                input_index,
                                self._int64_literal(node.loc, width),
                                node.loc,
                            ),
                        ),
                    ],
                    True,
                ),
            )

        decode = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                decode_arm(0x80, 1, 0x7F),
                decode_arm(0xE0, 2, 0x1F),
                decode_arm(0xF0, 3, 0x0F),
                decode_arm(None, 4, 0x07),
            ],
            None,
        )
        output_address = self._int64_binary(
            '__add__',
            data,
            self._int64_binary(
                '__mul__',
                output_index,
                self._int64_literal(node.loc, 4),
                node.loc,
            ),
            node.loc,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    node.loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        input_index,
                        byte_length,
                        node.loc,
                    ),
                    hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            decode,
                            self._intrinsic_call(
                                '__store_u32__',
                                [
                                    replace(scalar, type='uint32'),
                                    output_address,
                                ],
                                ty.VOID_TYPE,
                                node.loc,
                            ),
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                output_index,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    output_index,
                                    self._int64_literal(node.loc, 1),
                                    node.loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        allocator = '__static_alloca__'
        descriptor_word = replace(descriptor, type='int64')
        statements: list[hir.AST] = [
            *prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [
                        self._int64_binary(
                            '__mul__',
                            byte_length,
                            self._int64_literal(node.loc, 4),
                            node.loc,
                        )
                    ],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                input_index_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                output_index_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                scalar_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            loop,
            self._store_i64_field(
                descriptor_word,
                ARRAY_DATA_OFFSET,
                data,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_LENGTH_OFFSET,
                output_index,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_CAPACITY_OFFSET,
                byte_length,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(node.loc, 4),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(node.loc, ARRAY_MUTABLE),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_OWNER_OFFSET,
                self._int64_literal(node.loc, 0),
                node.loc,
            ),
        ]
        return statements, descriptor

    def _string_to_grapheme_array(
        self,
        node: hir.RepresentationCast,
        source: hir.AST,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        prelude, string = self._extract_expression(source)
        length = self._load_i64_field(
            string,
            STRING_GRAPHEME_LENGTH_OFFSET,
            node.loc,
        )
        descriptor = self._new_array_temp(hir.ArrayLiteral(node.loc, node.type, []))
        data_name = self._new_array_name('grapheme_data')
        views_name = self._new_string_temp(node.loc, 'int64', 'views').name
        index_name = self._new_array_name('grapheme_index')
        data = hir.ExpressedIdentifier(node.loc, 'int64', data_name)
        views = hir.ExpressedIdentifier(node.loc, 'int64', views_name)
        index = hir.ExpressedIdentifier(node.loc, 'int64', index_name)
        view = self._int64_binary(
            '__add__',
            views,
            self._int64_binary(
                '__mul__',
                index,
                self._int64_literal(node.loc, STRING_DESCRIPTOR_SIZE),
                node.loc,
            ),
            node.loc,
        )
        first_offset = self._string_boundary(string, index, node.loc)
        end_offset = self._string_boundary(
            string,
            self._int64_binary(
                '__add__',
                index,
                self._int64_literal(node.loc, 1),
                node.loc,
            ),
            node.loc,
        )
        boundaries = self._load_i64_field(
            string,
            STRING_BOUNDARIES_OFFSET,
            node.loc,
        )
        shifted_boundaries = self._int64_binary(
            '__add__',
            boundaries,
            self._int64_binary(
                '__mul__',
                index,
                self._int64_literal(node.loc, 4),
                node.loc,
            ),
            node.loc,
        )
        output_address = self._int64_binary(
            '__add__',
            data,
            self._int64_binary(
                '__mul__',
                index,
                self._int64_literal(node.loc, 8),
                node.loc,
            ),
            node.loc,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    node.loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', index, length, node.loc),
                    hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            self._store_i64_field(
                                view,
                                STRING_DATA_OFFSET,
                                self._load_i64_field(
                                    string,
                                    STRING_DATA_OFFSET,
                                    node.loc,
                                ),
                                node.loc,
                            ),
                            self._store_i64_field(
                                view,
                                STRING_BYTE_LENGTH_OFFSET,
                                self._int64_binary(
                                    '__sub__',
                                    end_offset,
                                    first_offset,
                                    node.loc,
                                ),
                                node.loc,
                            ),
                            self._store_i64_field(
                                view,
                                STRING_BOUNDARIES_OFFSET,
                                shifted_boundaries,
                                node.loc,
                            ),
                            self._store_i64_field(
                                view,
                                STRING_GRAPHEME_LENGTH_OFFSET,
                                self._int64_literal(node.loc, 1),
                                node.loc,
                            ),
                            self._store_i64_field(
                                view,
                                STRING_START_OFFSET,
                                first_offset,
                                node.loc,
                            ),
                            self._intrinsic_call(
                                '__store_i64__',
                                [view, output_address],
                                ty.VOID_TYPE,
                                node.loc,
                            ),
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                index,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    index,
                                    self._int64_literal(node.loc, 1),
                                    node.loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        allocator = (
            '__static_alloca__'
            if self.lowering_module_startup
            else '__alloca__'
        )
        descriptor_word = replace(descriptor, type='int64')
        return [
            *prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [
                        self._int64_binary(
                            '__mul__',
                            length,
                            self._int64_literal(node.loc, 8),
                            node.loc,
                        )
                    ],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                views_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [
                        self._int64_binary(
                            '__mul__',
                            length,
                            self._int64_literal(node.loc, STRING_DESCRIPTOR_SIZE),
                            node.loc,
                        )
                    ],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                index_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            loop,
            self._store_i64_field(
                descriptor_word,
                ARRAY_DATA_OFFSET,
                data,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_LENGTH_OFFSET,
                length,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_CAPACITY_OFFSET,
                length,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(node.loc, 8),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(node.loc, ARRAY_MUTABLE),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_OWNER_OFFSET,
                replace(string, type='int64'),
                node.loc,
            ),
        ], descriptor

    def _string_boundary(
        self,
        string: hir.AST,
        index: hir.AST,
        loc: Span,
    ) -> hir.AST:
        boundaries = self._load_i64_field(
            string,
            STRING_BOUNDARIES_OFFSET,
            loc,
        )
        offset = self._int64_binary(
            '__mul__',
            index,
            self._int64_literal(loc, 4),
            loc,
        )
        address = self._int64_binary('__add__', boundaries, offset, loc)
        return self._intrinsic_call('__load_u32__', [address], 'uint32', loc)

    def _string_view(
        self,
        string: hir.AST,
        first: hir.AST,
        count: hir.AST,
        type_: ty.Type,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        allocator = '__static_alloca__'
        target = self._new_string_temp(loc, type_, 'view')
        boundaries = self._load_i64_field(
            string,
            STRING_BOUNDARIES_OFFSET,
            loc,
        )
        first_offset = self._string_boundary(string, first, loc)
        end_index = self._int64_binary('__add__', first, count, loc)
        end_offset = self._string_boundary(string, end_index, loc)
        shifted_boundaries = self._int64_binary(
            '__add__',
            boundaries,
            self._int64_binary(
                '__mul__',
                first,
                self._int64_literal(loc, 4),
                loc,
            ),
            loc,
        )
        descriptor = replace(target, type='int64')
        return [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    loc,
                ),
            ),
            self._store_i64_field(
                descriptor,
                STRING_DATA_OFFSET,
                self._load_i64_field(string, STRING_DATA_OFFSET, loc),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                STRING_BYTE_LENGTH_OFFSET,
                self._int64_binary('__sub__', end_offset, first_offset, loc),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                STRING_BOUNDARIES_OFFSET,
                shifted_boundaries,
                loc,
            ),
            self._store_i64_field(
                descriptor,
                STRING_GRAPHEME_LENGTH_OFFSET,
                count,
                loc,
            ),
            self._store_i64_field(
                descriptor,
                STRING_START_OFFSET,
                first_offset,
                loc,
            ),
        ], target

    def _extract_string_index(
        self,
        node: hir.StringIndex,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        prelude, string = self._extract_expression(node.string)
        if node.constant_index is None:
            index_prelude, index = self._extract_expression(node.index)
            prelude.extend(index_prelude)
        else:
            index = self._int64_literal(node.loc, node.constant_index)
        view_prelude, view = self._string_view(
            string,
            index,
            self._int64_literal(node.loc, 1),
            node.type,
            node.loc,
        )
        return [*prelude, *view_prelude], view

    @staticmethod
    def _literal_index(node: hir.AST | None) -> int | None:
        if node is None:
            return None
        while isinstance(node, (hir.ValueCast, hir.RepresentationCast)):
            node = node.expr
        if isinstance(node, hir.Integer):
            return node.value
        if isinstance(node.type, ty.IntegerLiteralType):
            return node.type.value
        return None

    def _extract_string_slice(
        self,
        node: hir.StringSlice,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        prelude, string = self._extract_expression(node.string)
        length = self._load_i64_field(
            string,
            STRING_GRAPHEME_LENGTH_OFFSET,
            node.loc,
        )
        bounds = node.range.bounds or '[]'

        if node.range.left is None:
            first_expr: hir.AST = self._int64_literal(node.loc, 0)
        else:
            left_prelude, left = self._extract_expression(node.range.left)
            prelude.extend(left_prelude)
            first_expr = hir.ValueCast(left.loc, 'int64', left)
            if bounds[0] == '(':
                first_expr = self._int64_binary(
                    '__add__',
                    first_expr,
                    self._int64_literal(node.loc, 1),
                    node.loc,
                )
        first = self._new_string_temp(node.loc, 'int64', 'slice_first')
        prelude.append(hir.Declare(
            node.loc,
            ty.VOID_TYPE,
            'let',
            first.name,
            'int64',
            first_expr,
        ))

        if node.range.right is None:
            count = self._int64_binary('__sub__', length, first, node.loc)
        else:
            right_prelude, right = self._extract_expression(node.range.right)
            prelude.extend(right_prelude)
            last_expr: hir.AST = hir.ValueCast(right.loc, 'int64', right)
            if bounds[1] == ')':
                last_expr = self._int64_binary(
                    '__sub__',
                    last_expr,
                    self._int64_literal(node.loc, 1),
                    node.loc,
                )
            last = self._new_string_temp(node.loc, 'int64', 'slice_last')
            prelude.append(hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                last.name,
                'int64',
                last_expr,
            ))
            count_flow = hir.Flow(
                node.loc,
                'int64',
                [
                    hir.IfArm(
                        node.loc,
                        'int64',
                        self._int64_comparison('__lt__', last, first, node.loc),
                        self._int64_literal(node.loc, 0),
                    )
                ],
                self._int64_binary(
                    '__add__',
                    self._int64_binary('__sub__', last, first, node.loc),
                    self._int64_literal(node.loc, 1),
                    node.loc,
                ),
            )
            count_prelude, count = self._extract_expression(count_flow)
            prelude.extend(count_prelude)
        view_prelude, view = self._string_view(
            string,
            first,
            count,
            node.type,
            node.loc,
        )
        return [*prelude, *view_prelude], view

    def _extract_string_equal(
        self,
        node: hir.StringEqual,
    ) -> tuple[list[hir.AST], hir.AST]:
        left_prelude, left = self._extract_expression(node.left)
        right_prelude, right = self._extract_expression(node.right)
        left_length = self._load_i64_field(
            left,
            STRING_BYTE_LENGTH_OFFSET,
            node.loc,
        )
        right_length = self._load_i64_field(
            right,
            STRING_BYTE_LENGTH_OFFSET,
            node.loc,
        )
        result_name = self._new_string_temp(node.loc, 'bool', 'equal').name
        index_name = self._new_string_temp(node.loc, 'int64', 'equal_index').name
        result = hir.ExpressedIdentifier(node.loc, 'bool', result_name)
        index = hir.ExpressedIdentifier(node.loc, 'int64', index_name)
        left_data = self._string_data_start(left, node.loc)
        right_data = self._string_data_start(right, node.loc)
        left_byte = self._intrinsic_call(
            '__load_u8__',
            [self._int64_binary('__add__', left_data, index, node.loc)],
            'uint8',
            node.loc,
        )
        right_byte = self._intrinsic_call(
            '__load_u8__',
            [self._int64_binary('__add__', right_data, index, node.loc)],
            'uint8',
            node.loc,
        )
        byte_equal = self._typed_equality(
            left_byte,
            right_byte,
            'uint8',
            node.loc,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    node.loc,
                    ty.VOID_TYPE,
                    hir.ShortCircuit(
                        node.loc,
                        'bool',
                        'and',
                        self._int64_comparison(
                            '__lt__',
                            index,
                            left_length,
                            node.loc,
                        ),
                        result,
                    ),
                    hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                result,
                                '=',
                                byte_equal,
                            ),
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                index,
                                '=',
                                self._int64_binary(
                                    '__add__',
                                    index,
                                    self._int64_literal(node.loc, 1),
                                    node.loc,
                                ),
                            ),
                        ],
                        True,
                    ),
                )
            ],
            None,
        )
        initial = self._typed_equality(
            left_length,
            right_length,
            'int64',
            node.loc,
        )
        statements: list[hir.AST] = [
            *left_prelude,
            *right_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                result_name,
                'bool',
                initial,
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                index_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            loop,
        ]
        if node.negated:
            return statements, self._typed_equality(
                result,
                hir.Bool(node.loc, 'bool', False),
                'bool',
                node.loc,
            )
        return statements, result

    def _new_string_temp(
        self,
        loc: Span,
        type_: ty.Type,
        role: str = 'value',
    ) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_string_{role}_{self.next_string_temp}'
            self.next_string_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(loc, type_, name)

    def _lower_string_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
        iterator: hir.IteratorExpression,
    ) -> list[hir.AST]:
        prelude, string = self._extract_expression(iterator.iterable)
        offset = self._new_iterator_temp(iterator)
        target = replace(iterator.target, loc=iterator.loc, type='int64')
        offset_value = replace(offset, loc=iterator.loc)
        updates = [
            *self._string_iterator_view_updates(
                string,
                target,
                offset_value,
                iterator.loc,
            ),
            hir.Assign(
                iterator.loc,
                ty.VOID_TYPE,
                offset_value,
                '+=',
                self._int64_literal(iterator.loc, 1),
            ),
        ]
        self.lower_loop_depth += 1
        lowered_body = self._lower_statement_body(arm.body)
        self.lower_loop_depth -= 1
        body_items = (
            lowered_body.items
            if isinstance(lowered_body, hir.Block)
            else [lowered_body]
        )
        body = hir.Block(
            arm.body.loc,
            ty.VOID_TYPE,
            [*updates, *body_items],
            True,
        )
        length = self._load_i64_field(
            string,
            STRING_GRAPHEME_LENGTH_OFFSET,
            iterator.loc,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    arm.loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        offset_value,
                        length,
                        iterator.loc,
                    ),
                    body,
                )
            ],
            None,
        )
        return [
            *prelude,
            hir.Declare(
                iterator.loc,
                ty.VOID_TYPE,
                'let',
                offset.name,
                'int64',
                self._int64_literal(iterator.loc, 0),
            ),
            hir.Declare(
                iterator.target.loc,
                ty.VOID_TYPE,
                'let',
                iterator.target.name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(iterator.loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    iterator.loc,
                ),
                binding_id=iterator.target.binding_id,
            ),
            loop,
        ]

    def _string_iterator_view_updates(
        self,
        string: hir.AST,
        target: hir.AST,
        offset: hir.AST,
        loc: Span,
    ) -> list[hir.AST]:
        """Point one reusable string descriptor at the current grapheme."""

        first_offset = self._string_boundary(
            string,
            offset,
            loc,
        )
        end_offset = self._string_boundary(
            string,
            self._int64_binary(
                '__add__',
                offset,
                self._int64_literal(loc, 1),
                loc,
            ),
            loc,
        )
        boundaries = self._load_i64_field(
            string,
            STRING_BOUNDARIES_OFFSET,
            loc,
        )
        return [
            self._store_i64_field(
                target,
                STRING_DATA_OFFSET,
                self._load_i64_field(
                    string,
                    STRING_DATA_OFFSET,
                    loc,
                ),
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_BYTE_LENGTH_OFFSET,
                self._int64_binary(
                    '__sub__',
                    end_offset,
                    first_offset,
                    loc,
                ),
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_BOUNDARIES_OFFSET,
                self._int64_binary(
                    '__add__',
                    boundaries,
                    self._int64_binary(
                        '__mul__',
                        offset,
                        self._int64_literal(loc, 4),
                        loc,
                    ),
                    loc,
                ),
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_GRAPHEME_LENGTH_OFFSET,
                self._int64_literal(loc, 1),
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_START_OFFSET,
                first_offset,
                loc,
            ),
        ]

    def _string_iterator_target(
        self,
        iterator: hir.IteratorExpression,
        ordinal: hir.AST,
    ) -> tuple[list[hir.AST], list[hir.AST]]:
        loc = iterator.loc
        data_name = self._new_string_temp(loc, 'int64', 'range_data').name
        boundaries_name = self._new_string_temp(
            loc,
            'int64',
            'range_boundaries',
        ).name
        scalar_name = self._new_iterator_name('scalar')
        data = hir.ExpressedIdentifier(loc, 'int64', data_name)
        boundaries = hir.ExpressedIdentifier(loc, 'int64', boundaries_name)
        scalar = hir.ExpressedIdentifier(loc, 'int64', scalar_name)
        target = replace(iterator.target, loc=loc, type='int64')
        allocator = '__alloca__'
        declarations: list[hir.AST] = [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, 4)],
                    'int64',
                    loc,
                ),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                boundaries_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, 8)],
                    'int64',
                    loc,
                ),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                iterator.target.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    loc,
                ),
                binding_id=iterator.target.binding_id,
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                scalar_name,
                'int64',
                self._int64_literal(loc, 0),
            ),
            self._intrinsic_call(
                '__store_u32__',
                [hir.Integer(loc, 'uint32', t0.base10, 0), boundaries],
                ty.VOID_TYPE,
                loc,
            ),
            self._store_i64_field(target, STRING_DATA_OFFSET, data, loc),
            self._store_i64_field(
                target,
                STRING_BOUNDARIES_OFFSET,
                boundaries,
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_GRAPHEME_LENGTH_OFFSET,
                self._int64_literal(loc, 1),
                loc,
            ),
            self._store_i64_field(
                target,
                STRING_START_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
        ]
        scalar_update = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        ordinal,
                        self._int64_literal(loc, 0xD800),
                        loc,
                    ),
                    hir.Assign(loc, ty.VOID_TYPE, scalar, '=', ordinal),
                )
            ],
            hir.Assign(
                loc,
                ty.VOID_TYPE,
                scalar,
                '=',
                self._int64_binary(
                    '__add__',
                    ordinal,
                    self._int64_literal(loc, 0x800),
                    loc,
                ),
            ),
        )

        def shifted(mask: int, shift: int) -> hir.AST:
            value = (
                scalar
                if shift == 0
                else self._int64_binary(
                    '__rshift__',
                    scalar,
                    self._int64_literal(loc, shift),
                    loc,
                )
            )
            return self._int64_binary(
                '__and__',
                value,
                self._int64_literal(loc, mask),
                loc,
            )

        def utf8_byte(prefix: int, mask: int, shift: int) -> hir.AST:
            value = shifted(mask, shift)
            return (
                value
                if prefix == 0
                else self._int64_binary(
                    '__or__',
                    self._int64_literal(loc, prefix),
                    value,
                    loc,
                )
            )

        def store_byte(index: int, value: hir.AST) -> hir.AST:
            address = (
                data
                if index == 0
                else self._int64_binary(
                    '__add__',
                    data,
                    self._int64_literal(loc, index),
                    loc,
                )
            )
            return self._intrinsic_call(
                '__store_u8__',
                [replace(value, type='uint8'), address],
                ty.VOID_TYPE,
                loc,
            )

        def encode_arm(limit: int | None, values: list[hir.AST]) -> hir.IfArm:
            width = len(values)
            condition = (
                hir.Bool(loc, 'bool', True)
                if limit is None
                else self._int64_comparison(
                    '__lt__',
                    scalar,
                    self._int64_literal(loc, limit),
                    loc,
                )
            )
            return hir.IfArm(
                loc,
                ty.VOID_TYPE,
                condition,
                hir.Block(
                    loc,
                    ty.VOID_TYPE,
                    [
                        *[
                            store_byte(index, value)
                            for index, value in enumerate(values)
                        ],
                        self._store_i64_field(
                            target,
                            STRING_BYTE_LENGTH_OFFSET,
                            self._int64_literal(loc, width),
                            loc,
                        ),
                        self._intrinsic_call(
                            '__store_u32__',
                            [
                                hir.Integer(
                                    loc,
                                    'uint32',
                                    t0.base10,
                                    width,
                                ),
                                self._int64_binary(
                                    '__add__',
                                    boundaries,
                                    self._int64_literal(loc, 4),
                                    loc,
                                ),
                            ],
                            ty.VOID_TYPE,
                            loc,
                        ),
                    ],
                    True,
                ),
            )

        encode = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                encode_arm(0x80, [utf8_byte(0, 0x7F, 0)]),
                encode_arm(
                    0x800,
                    [
                        utf8_byte(0xC0, 0x1F, 6),
                        utf8_byte(0x80, 0x3F, 0),
                    ],
                ),
                encode_arm(
                    0x10000,
                    [
                        utf8_byte(0xE0, 0x0F, 12),
                        utf8_byte(0x80, 0x3F, 6),
                        utf8_byte(0x80, 0x3F, 0),
                    ],
                ),
                encode_arm(
                    None,
                    [
                        utf8_byte(0xF0, 0x07, 18),
                        utf8_byte(0x80, 0x3F, 12),
                        utf8_byte(0x80, 0x3F, 6),
                        utf8_byte(0x80, 0x3F, 0),
                    ],
                ),
            ],
            None,
        )
        return declarations, [scalar_update, encode]

