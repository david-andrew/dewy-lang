"""String, grapheme, and unicode lowering: literals, views, slicing, conversions, and string iteration.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace
from typing import Literal

from ...parser import t0
from ...reporting import Span
from ...semantic import hir, ty
from ...semantic.hir_display import type_to_dewy
from .lowering_shared import (
    ARGC_NAME,
    ARGV_NAME,
    ARRAY_BORROWED_STATIC,
    ARRAY_CAPACITY_OFFSET,
    ARRAY_DATA_OFFSET,
    ARRAY_DESCRIPTOR_SIZE,
    ARRAY_FLAGS_OFFSET,
    ARRAY_LENGTH_OFFSET,
    ARRAY_MUTABLE,
    ARRAY_OWNER_OFFSET,
    ARRAY_STRIDE_OFFSET,
    FIXED_INTEGER_WIDTHS,
    STRING_BOUNDARIES_OFFSET,
    STRING_BYTE_LENGTH_OFFSET,
    STRING_DATA_OFFSET,
    STRING_DESCRIPTOR_SIZE,
    STRING_GRAPHEME_LENGTH_OFFSET,
    STRING_START_OFFSET,
    StringResultBound,
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
        target_enum = ty.enum_members(target)
        if target_enum is not None:
            # a singleton or a narrower enum stored as this enum: the tag word
            return self._enum_word_of(source, target_enum)
        source_enum = self._enum_of(source)
        if source_enum is not None and ty.enum_members(source.type) is not None:
            # an enum meeting a string: its member's text
            return self._enum_text_of(source, source_enum)
        if (
            isinstance(source.type, ty.ArrayType)
            and source.type.element == 'uint8'
            and ty.optional_payload(target) is not None
        ):
            return self._decode_utf8_optional(node, source)
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

    def _unicode_table(self, table: str, role: str, loc: Span) -> hir.AST:
        """A Unicode property table as one module-level global.

        The tables are large (the grapheme-break table alone is ~50 KB) and
        every string that is segmented needs them, so each is emitted once
        as a packed byte literal stored into a hidden global at startup,
        and every lookup reads that global. (Inlining the text literal at
        each use made the generated program ~700 KB, 4 hex characters per
        byte, duplicated per lookup.)
        """
        name = f'__dewy_unicode_{role}'
        if name not in self.unicode_table_globals:
            data = table.encode('ascii')   # records are printable ASCII (`TABLE_BYTE_OFFSET` + 6-bit fields)
            self.unicode_table_globals[name] = hir.BasedString(loc, 'int64', t0.base16, data.hex(), data)
        return hir.ExpressedIdentifier(loc, 'int64', name)

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
            self._unicode_table(table, role, loc),
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

        segmentation, grapheme_count = self._utf8_segmentation(
            loc,
            data,
            byte_length,
            boundaries,
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
        ]
        return [
            *prelude,
            *declarations,
            *segmentation,
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

    @staticmethod
    def _is_string_valued(type_: object) -> bool:
        return isinstance(type_, (ty.StringType, ty.StringLiteralType)) or type_ in (
            'string',
            'grapheme',
            'char',
        )

    @staticmethod
    def _unwrap_transparent(node: hir.AST) -> hir.AST:
        while (
            isinstance(node, hir.Block)
            and not node.scoped
            and len(node.items) == 1
        ):
            node = node.items[0]
        return node

    def _analyze_string_results(self) -> None:
        """Bound string results and select caller-owned destination functions.

        Every string-returning function gets a capacity bound: a constant
        byte count plus per-parameter multiples of string argument lengths.
        Functions that may return frame-backed materialized strings switch to
        the destination ABI, where the caller allocates a result block sized
        by the bound and the callee writes the result through it.
        """
        self.string_result_bounds = {}
        self.string_result_needs_dest = set()
        self._string_bound_in_progress: set[int] = set()
        for function in self.functions:
            if self._is_string_valued(function.literal.rettype):
                self._function_string_bound(function)
        for function in self.functions:
            if id(function) not in self.string_result_needs_dest:
                continue
            if function.literal.object_receiver:
                self._target_error(
                    function.literal,
                    'an object method returning a materialized string',
                )
            if function.result_name is None:
                function.result_name = self._new_result_name()
        self._check_string_function_value_uses()

    def _function_string_bound(self, function) -> StringResultBound | None:
        key = id(function)
        if key in self.string_result_bounds:
            return self.string_result_bounds[key]
        if key in self._string_bound_in_progress:
            return None
        self._string_bound_in_progress.add(key)
        literal = function.literal
        returned = self._returned_string_expressions(literal)
        local_cache: dict[int, StringResultBound | None] = {}
        bound: StringResultBound | None = StringResultBound(0, (), False)
        materialized = False
        for expr in returned:
            expr_bound = self._string_value_bound(expr, literal, local_cache)
            if expr_bound is not None and expr_bound.materialized:
                materialized = True
            if bound is None or expr_bound is None:
                bound = None
            else:
                bound = bound.combined_max(expr_bound)
        self._string_bound_in_progress.discard(key)
        if materialized or any(
            isinstance(self._unwrap_transparent(expr), hir.InterpolatedString)
            for expr in returned
        ):
            self.string_result_needs_dest.add(key)
            if bound is None:
                self._target_error(
                    literal,
                    'a returned string whose size cannot be bounded at compile time',
                )
        self.string_result_bounds[key] = bound
        return bound

    def _returned_string_expressions(self, literal: hir.FunctionLiteral) -> list[hir.AST]:
        results: list[hir.AST] = []

        def note(expr: hir.AST) -> None:
            if self._is_string_valued(expr.type):
                results.append(expr)

        def trailing(expr: hir.AST) -> None:
            expr = self._unwrap_transparent(expr)
            if isinstance(expr, hir.Block):
                if expr.items:
                    trailing(expr.items[-1])
                return
            if isinstance(expr, hir.Flow):
                for arm in expr.arms:
                    trailing(arm.body)
                if expr.default is not None:
                    trailing(expr.default)
                return
            if isinstance(expr, hir.Return):
                return
            note(expr)

        def walk(node: object) -> None:
            if isinstance(node, hir.FunctionLiteral) and node is not literal:
                return
            if isinstance(node, hir.Return) and node.item is not None:
                note(node.item)
            if isinstance(node, hir.AST):
                for field_ in dataclasses.fields(node):
                    value = getattr(node, field_.name)
                    for child in (
                        value if isinstance(value, (list, tuple)) else [value]
                    ):
                        if isinstance(child, hir.AST):
                            walk(child)
                        elif isinstance(child, hir.ObjectField):
                            walk(child.value)
                        elif isinstance(child, dict):
                            for item in child.values():
                                walk(item)

        walk(literal.body)
        trailing(literal.body)
        return results

    def _string_local_candidates(
        self,
        literal: hir.FunctionLiteral,
    ) -> dict[int, list[hir.AST]]:
        candidates: dict[int, list[hir.AST]] = {}

        def walk(node: object) -> None:
            if isinstance(node, hir.FunctionLiteral) and node is not literal:
                return
            if (
                isinstance(node, hir.Declare)
                and node.binding_id is not None
                and self._is_string_valued(node.annotation or node.expr.type)
            ):
                candidates.setdefault(node.binding_id, []).append(node.expr)
            if (
                isinstance(node, hir.Assign)
                and node.target.binding_id is not None
                and self._is_string_valued(node.target.type)
            ):
                candidates.setdefault(node.target.binding_id, []).append(node.value)
            if isinstance(node, hir.AST):
                for field_ in dataclasses.fields(node):
                    value = getattr(node, field_.name)
                    for child in (
                        value if isinstance(value, (list, tuple)) else [value]
                    ):
                        if isinstance(child, hir.AST):
                            walk(child)
                        elif isinstance(child, hir.ObjectField):
                            walk(child.value)
                        elif isinstance(child, dict):
                            for item in child.values():
                                walk(item)

        walk(literal.body)
        return candidates

    def _string_value_bound(
        self,
        expr: hir.AST,
        literal: hir.FunctionLiteral,
        local_cache: dict[int, StringResultBound | None],
        _local_in_progress: set[int] | None = None,
    ) -> StringResultBound | None:
        in_progress = set() if _local_in_progress is None else _local_in_progress
        expr = self._unwrap_transparent(expr)
        if isinstance(expr, hir.String):
            return StringResultBound(len(expr.content.encode('utf-8')), (), False)
        if isinstance(expr.type, ty.StringLiteralType):
            return StringResultBound(
                len(expr.type.value.encode('utf-8')), (), False
            )
        if isinstance(expr, hir.InterpolatedString):
            bound = StringResultBound(0, (), True)
            for part in expr.parts:
                part_bound = self._string_part_bound(
                    part, literal, local_cache, in_progress
                )
                if part_bound is None:
                    return None
                bound = bound.combined_sum(part_bound)
            return bound
        if isinstance(expr, hir.ExpressedIdentifier):
            if expr.binding_id is not None:
                for index, param in enumerate(literal.pos_or_kw_args):
                    if param.binding_id == expr.binding_id:
                        return StringResultBound(0, ((index, 1),), False)
                if expr.binding_id in local_cache:
                    return local_cache[expr.binding_id]
                if expr.binding_id in in_progress:
                    return None
                candidates = self._string_local_candidates(literal).get(
                    expr.binding_id
                )
                if candidates:
                    in_progress.add(expr.binding_id)
                    bound: StringResultBound | None = StringResultBound(0, (), False)
                    for candidate in candidates:
                        candidate_bound = self._string_value_bound(
                            candidate, literal, local_cache, in_progress
                        )
                        if bound is None or candidate_bound is None:
                            bound = None
                        else:
                            bound = bound.combined_max(candidate_bound)
                    in_progress.discard(expr.binding_id)
                    local_cache[expr.binding_id] = bound
                    return bound
            return None
        if isinstance(expr, (hir.StringIndex, hir.StringSlice)):
            return self._string_value_bound(
                expr.string, literal, local_cache, in_progress
            )
        if isinstance(expr, hir.Flow):
            bound = StringResultBound(0, (), False)
            bodies = [arm.body for arm in expr.arms]
            if expr.default is not None:
                bodies.append(expr.default)
            for body in bodies:
                body_bound = self._string_value_bound(
                    body, literal, local_cache, in_progress
                )
                if body_bound is None:
                    return None
                bound = bound.combined_max(body_bound)
            return bound
        if isinstance(expr, hir.FunctionCall):
            callee = self._direct_call_function(expr)
            if callee is None:
                return None
            callee_bound = self._function_string_bound(callee)
            if callee_bound is None:
                return None
            # The call's result is copied into this frame, so it counts as
            # materialized storage; its size composes the callee bound with
            # bounds for this call's string arguments.
            composed = StringResultBound(callee_bound.const_bytes, (), True)
            for index, count in callee_bound.counts:
                params = callee.literal.pos_or_kw_args
                if index >= len(params):
                    return None
                argument = (
                    expr.pos_args[index]
                    if index < len(expr.pos_args)
                    else expr.kw_args.get(params[index].name)
                )
                if argument is None:
                    return None
                argument_bound = self._string_value_bound(
                    argument, literal, local_cache, in_progress
                )
                if argument_bound is None:
                    return None
                for _ in range(count):
                    composed = composed.combined_sum(argument_bound)
            return composed
        return None

    def _string_part_bound(
        self,
        part: hir.AST,
        literal: hir.FunctionLiteral,
        local_cache: dict[int, StringResultBound | None],
        in_progress: set[int],
    ) -> StringResultBound | None:
        part_type = part.type
        if isinstance(part_type, ty.IntegerLiteralType):
            return StringResultBound(len(str(part_type.value)), (), False)
        if part_type == 'bool':
            return StringResultBound(5, (), False)
        if isinstance(part_type, str) and (
            part_type == 'int' or part_type in FIXED_INTEGER_WIDTHS
        ):
            return StringResultBound(20, (), False)
        if self._is_string_valued(part_type):
            return self._string_value_bound(
                part, literal, local_cache, in_progress
            )
        return None

    def _check_string_function_value_uses(self) -> None:
        """Reject destination-ABI functions escaping as first-class values.

        Their lowered signature carries a hidden result parameter, so an
        indirect call through a plain function type would corrupt memory.
        """
        call_positions: set[int] = set()

        def mark(node: object) -> None:
            if (
                isinstance(node, hir.FunctionCall)
                and self._direct_call_function(node) is not None
            ):
                func = self._unwrap_transparent(node.func)
                call_positions.add(id(func))
            if isinstance(node, hir.AST):
                for field_ in dataclasses.fields(node):
                    value = getattr(node, field_.name)
                    for child in (
                        value if isinstance(value, (list, tuple)) else [value]
                    ):
                        if isinstance(child, hir.AST):
                            mark(child)
                        elif isinstance(child, hir.ObjectField):
                            mark(child.value)
                        elif isinstance(child, dict):
                            for item in child.values():
                                mark(item)

        def check(node: object) -> None:
            if isinstance(node, hir.ExpressedIdentifier) and id(node) not in call_positions:
                binding = self.identifier_bindings.get(id(node))
                if (
                    binding is not None
                    and binding.kind == 'function'
                    and binding.function is not None
                    and id(binding.function) in self.string_result_needs_dest
                ):
                    self._target_error(
                        node,
                        'a function returning a materialized string used as a value',
                    )
            if (
                isinstance(node, hir.FunctionLiteral)
                and id(node) not in call_positions
            ):
                function = self.function_by_literal.get(id(node))
                if (
                    function is not None
                    and id(function) in self.string_result_needs_dest
                    and function.logical_name == 'anon'
                ):
                    self._target_error(
                        node,
                        'a function literal returning a materialized string used as a value',
                    )
            if isinstance(node, hir.AST):
                for field_ in dataclasses.fields(node):
                    value = getattr(node, field_.name)
                    for child in (
                        value if isinstance(value, (list, tuple)) else [value]
                    ):
                        if isinstance(child, hir.AST):
                            check(child)
                        elif isinstance(child, hir.ObjectField):
                            check(child.value)
                        elif isinstance(child, dict):
                            for item in child.values():
                                check(item)

        mark(self.root)
        check(self.root)

    def _string_result_write(self, item: hir.AST) -> list[hir.AST]:
        """Write one returned string into the caller-owned result block."""
        if self.current_string_result is None:
            raise TypeError('INTERNAL ERROR: missing string result cell')
        node = self._unwrap_transparent(item)
        if not isinstance(node, hir.InterpolatedString):
            # A single-field interpolation is exactly "copy this string value
            # with re-segmentation", which keeps one unified write path.
            node = hir.InterpolatedString(item.loc, ty.StringType(), [item])
        statements, _result = self._materialize_interpolated_string(
            node,
            dest=self.current_string_result,
        )
        return [
            *statements,
            hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
        ]

    def _finish_string_call(
        self,
        node: hir.FunctionCall,
        func: hir.AST,
        pos_args: list[hir.AST],
        kw_args: dict[str, hir.AST],
        prelude: list[hir.AST],
        function,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate and pre-point a caller-owned string result block.

        Layout: 40-byte descriptor, then ``(capacity + 1) * 4`` boundary
        bytes, then ``capacity + 1`` data bytes. The descriptor's data and
        boundaries fields are initialized to point into the block so the
        callee can materialize through them.
        """
        loc = node.loc
        bound = self.string_result_bounds.get(id(function))
        if bound is None:
            self._target_error(
                node,
                'a string result whose size cannot be bounded at compile time',
            )
        capacity: hir.AST = self._int64_literal(loc, bound.const_bytes)
        params = function.literal.pos_or_kw_args
        for index, count in bound.counts:
            if count == 0:
                continue
            parameter = params[index] if index < len(params) else None
            if parameter is None or isinstance(parameter, hir.BoundParam):
                self._target_error(
                    node,
                    'a string result sized by a defaulted string parameter',
                )
            # Normalized calls give every optional parameter a value slot and
            # a presence-flag slot, so map the parameter index to its slot.
            slot = index + sum(
                1
                for previous in params[:index]
                if isinstance(previous, hir.BoundParam)
            )
            argument = pos_args[slot] if slot < len(pos_args) else None
            if argument is None:
                self._target_error(
                    node,
                    'a string result capacity argument that cannot be located',
                )
            if not isinstance(argument, hir.ExpressedIdentifier):
                bound_name = self._new_string_temp(loc, 'int64', 'capacity_arg').name
                prelude.append(
                    hir.Declare(loc, ty.VOID_TYPE, 'let', bound_name, 'int64', argument)
                )
                argument = hir.ExpressedIdentifier(loc, 'int64', bound_name)
                pos_args[slot] = argument
            term: hir.AST = self._load_i64_field(
                replace(argument, type='int64'),
                STRING_BYTE_LENGTH_OFFSET,
                loc,
            )
            if count != 1:
                term = self._int64_binary(
                    '__mul__', term, self._int64_literal(loc, count), loc
                )
            capacity = self._int64_binary('__add__', capacity, term, loc)
        capacity_name = self._new_string_temp(loc, 'int64', 'result_capacity').name
        capacity_ident = hir.ExpressedIdentifier(loc, 'int64', capacity_name)
        result = self._new_string_temp(loc, node.type, 'result_block')
        result_word = replace(result, type='int64')
        boundaries_pointer = self._int64_binary(
            '__add__',
            result_word,
            self._int64_literal(loc, STRING_DESCRIPTOR_SIZE),
            loc,
        )
        data_pointer = self._int64_binary(
            '__add__',
            boundaries_pointer,
            self._int64_binary(
                '__mul__',
                self._int64_binary(
                    '__add__', capacity_ident, self._int64_literal(loc, 1), loc
                ),
                self._int64_literal(loc, 4),
                loc,
            ),
            loc,
        )
        prelude.extend([
            hir.Declare(loc, ty.VOID_TYPE, 'let', capacity_name, 'int64', capacity),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                result.name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [
                        self._int64_binary(
                            '__add__',
                            self._int64_binary(
                                '__mul__',
                                capacity_ident,
                                self._int64_literal(loc, 5),
                                loc,
                            ),
                            self._int64_literal(loc, STRING_DESCRIPTOR_SIZE + 5),
                            loc,
                        )
                    ],
                    'int64',
                    loc,
                ),
            ),
            self._store_i64_field(
                result_word,
                STRING_BOUNDARIES_OFFSET,
                boundaries_pointer,
                loc,
            ),
            self._store_i64_field(result_word, STRING_DATA_OFFSET, data_pointer, loc),
            self._store_i64_field(
                result_word,
                STRING_BYTE_LENGTH_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
            self._store_i64_field(
                result_word,
                STRING_GRAPHEME_LENGTH_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
            self._store_i64_field(
                result_word,
                STRING_START_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
            replace(
                node,
                type=ty.VOID_TYPE,
                func=func,
                pos_args=[*pos_args, result_word],
                kw_args=kw_args,
            ),
        ])
        return prelude, result

    def _utf8_segmentation(
        self,
        loc: Span,
        data: hir.ExpressedIdentifier,
        byte_length: hir.ExpressedIdentifier,
        boundaries: hir.ExpressedIdentifier,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Emit UAX #29 grapheme segmentation over a UTF-8 byte buffer.

        Stores ``uint32`` boundary byte offsets into ``boundaries`` (a
        leading 0, one entry per grapheme start, and a final
        ``byte_length`` entry) and returns the statements together with
        the identifier holding the grapheme count. ``boundaries`` must
        provide ``(byte_length + 1) * 4`` bytes of storage.
        """
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
            self._intrinsic_call(
                '__store_u32__',
                [hir.Integer(loc, 'uint32', t0.base10, 0), boundaries],
                ty.VOID_TYPE,
                loc,
            ),
            *[
                hir.Declare(loc, ty.VOID_TYPE, 'let', name, type_, value)
                for name, type_, value in state_declarations
            ],
            scan_loop,
            final_boundary,
        ], grapheme_count

    def _byte_copy_loop(self, dest: hir.AST, source: hir.AST, length: hir.AST, loc: Span) -> list[hir.AST]:
        """`loop i <? length { dest[i] = source[i] }` over bytes."""
        index = hir.ExpressedIdentifier(loc, 'int64', self._new_string_temp(loc, 'int64', 'copy_index').name)
        return [
            hir.Declare(loc, ty.VOID_TYPE, 'let', index.name, 'int64', self._int64_literal(loc, 0)),
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._int64_comparison('__lt__', index, length, loc),
                    hir.Block(loc, ty.VOID_TYPE, [
                        self._intrinsic_call(
                            '__store_u8__',
                            [
                                self._intrinsic_call('__load_u8__', [self._int64_binary('__add__', source, index, loc)], 'uint8', loc),
                                self._int64_binary('__add__', dest, index, loc),
                            ],
                            ty.VOID_TYPE,
                            loc,
                        ),
                        hir.Assign(loc, ty.VOID_TYPE, index, '=', self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc)),
                    ], True),
                )],
                None,
            ),
        ]

    def _join_string_array(
        self,
        node: hir.FunctionCall,
        method: hir.ArrayMethod,
        array_type: ty.ArrayType,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """`xs.join` / `xs.join(sep)`: concatenate string elements into a new
        arena-backed string (so the result outlives the frame and can be
        returned or stored), re-segmented so clusters may span the joins."""
        loc = node.loc
        statements: list[hir.AST] = []

        def declare(suffix: str, value: hir.AST) -> hir.ExpressedIdentifier:
            name = self._new_string_temp(loc, 'int64', suffix).name
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', name, 'int64', value))
            return hir.ExpressedIdentifier(loc, 'int64', name)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.AST:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        def add(left: hir.AST, right: hir.AST) -> hir.AST:
            return self._int64_binary('__add__', left, right, loc)

        prelude, array = self._extract_expression(method.array)
        statements.extend(prelude)
        array_word = replace(array, type='int64') if isinstance(array, hir.ExpressedIdentifier) else array
        count = declare('join_count', self._load_i64_field(array_word, ARRAY_LENGTH_OFFSET, loc))
        data = declare('join_data', self._load_i64_field(array_word, ARRAY_DATA_OFFSET, loc))
        separator_arg = self._optional_method_argument(node, 'sep')
        separator: hir.ExpressedIdentifier | None = None
        separator_length: hir.ExpressedIdentifier | None = None
        if separator_arg is not None:
            sep_prelude, sep_value = self._extract_expression(separator_arg)
            statements.extend(sep_prelude)
            separator = declare('join_sep', replace(sep_value, type='int64') if isinstance(sep_value, hir.ExpressedIdentifier) else sep_value)
            separator_length = declare('join_sep_length', self._load_i64_field(separator, STRING_BYTE_LENGTH_OFFSET, loc))

        def element(index: hir.AST) -> hir.AST:
            return self._intrinsic_call(
                '__load_i64__',
                [self._pointer_element_address(data, index, 8, loc)],
                'int64',
                loc,
            )

        # total bytes: every element, plus a separator between neighbours
        total = declare('join_total', self._int64_literal(loc, 0))
        index = declare('join_index', self._int64_literal(loc, 0))
        sum_body: list[hir.AST] = [
            assign(total, add(total, self._load_i64_field(element(index), STRING_BYTE_LENGTH_OFFSET, loc))),
            assign(index, add(index, self._int64_literal(loc, 1))),
        ]
        statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
            loc, ty.VOID_TYPE, self._int64_comparison('__lt__', index, count, loc), hir.Block(loc, ty.VOID_TYPE, sum_body, True),
        )], None))
        if separator_length is not None:
            statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                loc, ty.VOID_TYPE,
                self._int64_comparison('__gt__', count, self._int64_literal(loc, 1), loc),
                hir.Block(loc, ty.VOID_TYPE, [assign(total, add(total, self._int64_binary(
                    '__mul__', separator_length, self._int64_binary('__sub__', count, self._int64_literal(loc, 1), loc), loc,
                )))], True),
            )], None))
        out = declare('join_out', self._arena_allocation(add(total, self._int64_literal(loc, 1)), loc))
        cursor = declare('join_cursor', self._int64_literal(loc, 0))
        statements.append(assign(index, self._int64_literal(loc, 0)))
        piece = declare('join_piece', self._int64_literal(loc, 0))
        piece_length = declare('join_piece_length', self._int64_literal(loc, 0))
        copy_body: list[hir.AST] = []
        if separator is not None and separator_length is not None:
            copy_body.append(hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                loc, ty.VOID_TYPE,
                self._int64_comparison('__gt__', index, self._int64_literal(loc, 0), loc),
                hir.Block(loc, ty.VOID_TYPE, [
                    *self._byte_copy_loop(add(out, cursor), self._string_data_start(separator, loc), separator_length, loc),
                    assign(cursor, add(cursor, separator_length)),
                ], True),
            )], None))
        copy_body.extend([
            assign(piece, element(index)),
            assign(piece_length, self._load_i64_field(piece, STRING_BYTE_LENGTH_OFFSET, loc)),
            *self._byte_copy_loop(add(out, cursor), self._string_data_start(piece, loc), piece_length, loc),
            assign(cursor, add(cursor, piece_length)),
            assign(index, add(index, self._int64_literal(loc, 1))),
        ])
        statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
            loc, ty.VOID_TYPE, self._int64_comparison('__lt__', index, count, loc), hir.Block(loc, ty.VOID_TYPE, copy_body, True),
        )], None))
        boundaries = declare('join_boundaries', self._arena_allocation(
            self._int64_binary('__mul__', add(total, self._int64_literal(loc, 1)), self._int64_literal(loc, 4), loc), loc,
        ))
        segmentation, grapheme_count = self._utf8_segmentation(loc, out, total, boundaries)
        statements.extend(segmentation)
        descriptor = self._new_string_temp(loc, ty.StringType(), 'joined')
        descriptor_word = replace(descriptor, type='int64')
        statements.extend([
            hir.Declare(loc, ty.VOID_TYPE, 'let', descriptor.name, 'int64', self._arena_allocation(self._int64_literal(loc, STRING_DESCRIPTOR_SIZE), loc)),
            self._store_i64_field(descriptor_word, STRING_DATA_OFFSET, out, loc),
            self._store_i64_field(descriptor_word, STRING_BYTE_LENGTH_OFFSET, total, loc),
            self._store_i64_field(descriptor_word, STRING_BOUNDARIES_OFFSET, boundaries, loc),
            self._store_i64_field(descriptor_word, STRING_GRAPHEME_LENGTH_OFFSET, grapheme_count, loc),
            self._store_i64_field(descriptor_word, STRING_START_OFFSET, self._int64_literal(loc, 0), loc),
        ])
        return statements, descriptor

    def _decode_utf8_optional(
        self,
        node: hir.RepresentationCast,
        source: hir.AST,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """`bytes as string | undefined`: validate UTF-8 (RFC 3629: no overlongs,
        no surrogates, nothing above U+10FFFF), then build an arena string, else
        `undefined`. The result is an optional cell."""
        loc = node.loc
        statements: list[hir.AST] = []

        def declare(suffix: str, type_: str, value: hir.AST) -> hir.ExpressedIdentifier:
            name = self._new_string_temp(loc, type_, suffix).name
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', name, type_, value))
            return hir.ExpressedIdentifier(loc, type_, name)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.AST:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        prelude, array = self._extract_expression(source)
        statements.extend(prelude)
        array_word = replace(array, type='int64') if isinstance(array, hir.ExpressedIdentifier) else array
        length = declare('decode_length', 'int64', self._load_i64_field(array_word, ARRAY_LENGTH_OFFSET, loc))
        data = declare('decode_data', 'int64', self._load_i64_field(array_word, ARRAY_DATA_OFFSET, loc))
        index = declare('decode_index', 'int64', self._int64_literal(loc, 0))
        valid = declare('decode_valid', 'bool', hir.Bool(loc, 'bool', True))

        def byte_at(delta: int) -> hir.AST:
            address = self._int64_binary('__add__', data, index, loc)
            if delta:
                address = self._int64_binary('__add__', address, self._int64_literal(loc, delta), loc)
            return hir.ValueCast(loc, 'int64', self._intrinsic_call('__load_u8__', [address], 'uint8', loc))

        def between(value: hir.AST, low: int, high: int) -> hir.AST:
            return hir.ShortCircuit(
                loc, 'bool', 'and',
                self._int64_comparison('__ge__', value, self._int64_literal(loc, low), loc),
                self._int64_comparison('__le__', value, self._int64_literal(loc, high), loc),
            )

        def sequence(width: int, second: tuple[int, int]) -> hir.Block:
            # the lead byte is accepted; the continuation bytes must exist and fit
            conditions: list[hir.AST] = [self._int64_comparison(
                '__le__', self._int64_binary('__add__', index, self._int64_literal(loc, width), loc), length, loc,
            )]
            ranges = [second] + [(0x80, 0xBF)] * (width - 2)
            for delta, (low, high) in enumerate(ranges, start=1):
                conditions.append(between(byte_at(delta), low, high))
            condition: hir.AST = conditions[0]
            for extra in conditions[1:]:
                condition = hir.ShortCircuit(loc, 'bool', 'and', condition, extra)
            return hir.Block(loc, ty.VOID_TYPE, [hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                loc, ty.VOID_TYPE, condition,
                hir.Block(loc, ty.VOID_TYPE, [assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, width), loc))], True),
            )], hir.Block(loc, ty.VOID_TYPE, [assign(valid, hir.Bool(loc, 'bool', False))], True))], True)

        lead = byte_at(0)
        arms = [
            hir.IfArm(loc, ty.VOID_TYPE, self._int64_comparison('__lt__', lead, self._int64_literal(loc, 0x80), loc),
                      hir.Block(loc, ty.VOID_TYPE, [assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc))], True)),
            hir.IfArm(loc, ty.VOID_TYPE, between(lead, 0xC2, 0xDF), sequence(2, (0x80, 0xBF))),
            hir.IfArm(loc, ty.VOID_TYPE, self._int64_comparison('__eq__', lead, self._int64_literal(loc, 0xE0), loc), sequence(3, (0xA0, 0xBF))),
            hir.IfArm(loc, ty.VOID_TYPE, self._int64_comparison('__eq__', lead, self._int64_literal(loc, 0xED), loc), sequence(3, (0x80, 0x9F))),
            hir.IfArm(loc, ty.VOID_TYPE, between(lead, 0xE1, 0xEF), sequence(3, (0x80, 0xBF))),
            hir.IfArm(loc, ty.VOID_TYPE, self._int64_comparison('__eq__', lead, self._int64_literal(loc, 0xF0), loc), sequence(4, (0x90, 0xBF))),
            hir.IfArm(loc, ty.VOID_TYPE, self._int64_comparison('__eq__', lead, self._int64_literal(loc, 0xF4), loc), sequence(4, (0x80, 0x8F))),
            hir.IfArm(loc, ty.VOID_TYPE, between(lead, 0xF1, 0xF3), sequence(4, (0x80, 0xBF))),
        ]
        statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
            loc, ty.VOID_TYPE,
            hir.ShortCircuit(loc, 'bool', 'and', valid, self._int64_comparison('__lt__', index, length, loc)),
            hir.Block(loc, ty.VOID_TYPE, [hir.Flow(loc, ty.VOID_TYPE, arms, hir.Block(loc, ty.VOID_TYPE, [assign(valid, hir.Bool(loc, 'bool', False))], True))], True),
        )], None))
        cell = declare('decoded', 'int64', self._optional_allocation(loc))
        build, descriptor = self._string_from_bytes(data, length, loc)
        statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
            loc, ty.VOID_TYPE, valid,
            hir.Block(loc, ty.VOID_TYPE, [
                *build,
                self._intrinsic_call('__store_u8__', [self._uint8_literal(loc, 1), cell], ty.VOID_TYPE, loc),
                self._intrinsic_call('__store_i64__', [replace(descriptor, type='int64'), self._optional_payload_address(cell, loc)], ty.VOID_TYPE, loc),
            ], True),
        )], hir.Block(loc, ty.VOID_TYPE, [
            self._intrinsic_call('__store_u8__', [self._uint8_literal(loc, 0), cell], ty.VOID_TYPE, loc),
            self._intrinsic_call('__store_i64__', [self._int64_literal(loc, 0), self._optional_payload_address(cell, loc)], ty.VOID_TYPE, loc),
        ], True)))
        return statements, cell

    def _string_from_bytes(
        self,
        data_pointer: hir.AST,
        byte_length: hir.ExpressedIdentifier,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Copy ``byte_length`` bytes into the arena and build a segmented string."""
        statements: list[hir.AST] = []

        def declare(suffix: str, value: hir.AST) -> hir.ExpressedIdentifier:
            name = self._new_string_temp(loc, 'int64', suffix).name
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', name, 'int64', value))
            return hir.ExpressedIdentifier(loc, 'int64', name)

        data = declare(
            'data',
            self._arena_allocation(
                self._int64_binary('__add__', byte_length, self._int64_literal(loc, 1), loc), loc
            ),
        )
        index = declare('copy_index', self._int64_literal(loc, 0))
        statements.append(
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [
                    hir.LoopArm(
                        loc,
                        ty.VOID_TYPE,
                        self._int64_comparison('__lt__', index, byte_length, loc),
                        hir.Block(
                            loc,
                            ty.VOID_TYPE,
                            [
                                self._intrinsic_call(
                                    '__store_u8__',
                                    [
                                        self._intrinsic_call(
                                            '__load_u8__',
                                            [self._int64_binary('__add__', data_pointer, index, loc)],
                                            'uint8',
                                            loc,
                                        ),
                                        self._int64_binary('__add__', data, index, loc),
                                    ],
                                    ty.VOID_TYPE,
                                    loc,
                                ),
                                hir.Assign(
                                    loc,
                                    ty.VOID_TYPE,
                                    index,
                                    '=',
                                    self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc),
                                ),
                            ],
                            True,
                        ),
                    )
                ],
                None,
            )
        )
        boundaries = declare(
            'boundaries',
            self._arena_allocation(
                self._int64_binary(
                    '__mul__',
                    self._int64_binary('__add__', byte_length, self._int64_literal(loc, 1), loc),
                    self._int64_literal(loc, 4),
                    loc,
                ),
                loc,
            ),
        )
        segmentation, grapheme_count = self._utf8_segmentation(loc, data, byte_length, boundaries)
        statements.extend(segmentation)
        descriptor = self._new_string_temp(loc, ty.StringType())
        descriptor_word = replace(descriptor, type='int64')
        statements.extend([
            hir.Declare(
                loc, ty.VOID_TYPE, 'let', descriptor.name, 'int64',
                self._arena_allocation(self._int64_literal(loc, STRING_DESCRIPTOR_SIZE), loc),
            ),
            self._store_i64_field(descriptor_word, STRING_DATA_OFFSET, data, loc),
            self._store_i64_field(descriptor_word, STRING_BYTE_LENGTH_OFFSET, byte_length, loc),
            self._store_i64_field(descriptor_word, STRING_BOUNDARIES_OFFSET, boundaries, loc),
            self._store_i64_field(descriptor_word, STRING_GRAPHEME_LENGTH_OFFSET, grapheme_count, loc),
            self._store_i64_field(descriptor_word, STRING_START_OFFSET, self._int64_literal(loc, 0), loc),
        ])
        return statements, descriptor

    def _build_argv_prologue(self, loc: Span) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Turn the C ``argc``/``argv`` into a growable ``array<string>``."""
        argc = hir.ExpressedIdentifier(loc, 'int64', ARGC_NAME)
        argv = hir.ExpressedIdentifier(loc, 'int64', ARGV_NAME)
        element = ty.StringType()
        array_type = ty.ArrayType(element, None)
        statements, args = self._allocate_array_value(ty.ArrayType(element, 0), loc)
        args_array = replace(args, type=array_type)
        index = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('argv_index'))
        pointer = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('argv_pointer'))
        length = hir.ExpressedIdentifier(loc, 'int64', self._new_string_temp(loc, 'int64', 'argv_length').name)
        strlen_loop = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    loc,
                    ty.VOID_TYPE,
                    self._bool_not(
                        self._typed_equality(
                            replace(
                                self._intrinsic_call(
                                    '__load_u8__',
                                    [self._int64_binary('__add__', pointer, length, loc)],
                                    'uint8',
                                    loc,
                                ),
                                type='int64',
                            ),
                            self._int64_literal(loc, 0),
                            'int64',
                            loc,
                        )
                    ),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [hir.Assign(loc, ty.VOID_TYPE, length, '=', self._int64_binary('__add__', length, self._int64_literal(loc, 1), loc))],
                        True,
                    ),
                )
            ],
            None,
        )
        string_statements, string = self._string_from_bytes(pointer, length, loc)
        push_method = hir.ArrayMethod(
            loc,
            ty.FunctionType([ty.PosOrKwArg('value', element)], [], None, ty.VOID_TYPE),
            args_array,
            'push',
        )
        push_prelude, push = self._extract_array_method_call(
            hir.FunctionCall(loc, ty.VOID_TYPE, push_method, [string], {})
        )
        body = hir.Block(
            loc,
            ty.VOID_TYPE,
            [
                hir.Declare(
                    loc, ty.VOID_TYPE, 'let', pointer.name, 'int64',
                    self._intrinsic_call(
                        '__load_i64__',
                        [self._int64_binary('__add__', argv, self._int64_binary('__mul__', index, self._int64_literal(loc, 8), loc), loc)],
                        'int64',
                        loc,
                    ),
                ),
                hir.Declare(loc, ty.VOID_TYPE, 'let', length.name, 'int64', self._int64_literal(loc, 0)),
                strlen_loop,
                *string_statements,
                *push_prelude,
                push,
                hir.Assign(loc, ty.VOID_TYPE, index, '=', self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc)),
            ],
            True,
        )
        statements.extend([
            hir.Declare(loc, ty.VOID_TYPE, 'let', index.name, 'int64', self._int64_literal(loc, 0)),
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [hir.LoopArm(loc, ty.VOID_TYPE, self._int64_comparison('__lt__', index, argc, loc), body)],
                None,
            ),
        ])
        return statements, args_array

    def _materialize_interpolated_string(
        self,
        node: hir.InterpolatedString,
        dest: hir.ExpressedIdentifier | None = None,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Build one contiguous runtime string from interpolated parts.

        Writes every part's UTF-8 bytes into a byte buffer, then runs UAX #29
        segmentation so the result is a complete string descriptor with
        correct grapheme boundaries even when clusters span part joins.

        Without ``dest`` the storage lives in the current frame. With ``dest``
        — a caller-owned result block whose descriptor already points its
        ``data`` and ``boundaries`` fields at caller storage sized by the
        function's string-result capacity formula — the bytes, boundaries,
        and descriptor fields are written through ``dest`` instead, so the
        result survives the return.
        """
        loc = node.loc
        statements: list[hir.AST] = []
        # Module-startup values outlive the startup frame, so their storage
        # must be static — which needs a compile-time capacity computed from
        # the parts. Everything else lives in the current frame with runtime
        # sizing.
        allocator = (
            '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        )
        static_capacity: int | None = None
        if self.lowering_module_startup and dest is None:
            static_capacity = 0
            for part in node.parts:
                part_type = part.type
                if isinstance(part_type, ty.IntegerLiteralType):
                    static_capacity += len(str(part_type.value))
                elif part_type == 'bool':
                    static_capacity += 5
                elif isinstance(part_type, str) and (
                    part_type == 'int' or part_type in FIXED_INTEGER_WIDTHS
                ):
                    static_capacity += 20
                elif isinstance(part_type, ty.StringLiteralType):
                    static_capacity += len(part_type.value.encode('utf-8'))
                elif isinstance(part, hir.String):
                    static_capacity += len(part.content.encode('utf-8'))
                else:
                    self._target_error(
                        part,
                        'a module-level interpolated string field without a '
                        'compile-time size bound',
                    )
        # Each piece normalizes to a (length, source byte pointer) pair of
        # frame-local int64 bindings.
        pieces: list[tuple[hir.ExpressedIdentifier, hir.ExpressedIdentifier]] = []

        def declare(suffix: str, type_: str, value: hir.AST) -> hir.ExpressedIdentifier:
            name = self._new_string_temp(loc, type_, suffix).name
            statements.append(
                hir.Declare(loc, ty.VOID_TYPE, 'let', name, type_, value)
            )
            return hir.ExpressedIdentifier(loc, type_, name)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.AST:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        def add_piece(length: hir.AST, source: hir.AST) -> None:
            pieces.append((
                declare('piece_length', 'int64', length),
                declare('piece_source', 'int64', source),
            ))

        def string_piece(part: hir.AST) -> None:
            prelude, descriptor = self._extract_expression(part)
            statements.extend(prelude)
            word = (
                replace(descriptor, type='int64')
                if isinstance(descriptor, hir.ExpressedIdentifier)
                else descriptor
            )
            add_piece(
                self._load_i64_field(word, STRING_BYTE_LENGTH_OFFSET, loc),
                self._string_data_start(word, loc),
            )

        def static_text(content: str) -> hir.ExpressedIdentifier:
            prelude, descriptor = self._extract_string_literal(
                hir.String(loc, ty.StringLiteralType(content), content)
            )
            statements.extend(prelude)
            return replace(descriptor, type='int64')

        def bool_piece(part: hir.AST) -> None:
            prelude, value = self._extract_expression(part)
            statements.extend(prelude)
            true_text = static_text('true')
            false_text = static_text('false')
            selected = declare('bool_text', 'int64', false_text)
            statements.append(
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [hir.IfArm(loc, ty.VOID_TYPE, value, assign(selected, true_text))],
                    None,
                )
            )
            add_piece(
                self._load_i64_field(selected, STRING_BYTE_LENGTH_OFFSET, loc),
                self._string_data_start(selected, loc),
            )

        def store_digit(value: hir.AST, address: hir.AST) -> hir.AST:
            return self._intrinsic_call(
                '__store_u8__',
                [replace(value, type='uint8'), address],
                ty.VOID_TYPE,
                loc,
            )

        def integer_piece(part: hir.AST) -> None:
            prelude, raw = self._extract_expression(part)
            statements.extend(prelude)
            digits = declare(
                'digits',
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, 20)],
                    'int64',
                    loc,
                ),
            )
            position = declare('digit_position', 'int64', self._int64_literal(loc, 20))
            value = declare(
                'digit_value',
                'int64',
                raw if raw.type == 'int64' else replace(raw, type='int64'),
            )
            negative = declare(
                'digit_negative',
                'bool',
                self._int64_comparison('__lt__', value, self._int64_literal(loc, 0), loc),
            )
            source = declare('piece_source', 'int64', self._int64_literal(loc, 0))
            length = declare('piece_length', 'int64', self._int64_literal(loc, 0))
            minimum_text = static_text('-9223372036854775808')

            def emit_digit() -> list[hir.AST]:
                return [
                    assign(
                        position,
                        self._int64_binary(
                            '__sub__', position, self._int64_literal(loc, 1), loc
                        ),
                    ),
                    store_digit(
                        self._int64_binary(
                            '__add__',
                            self._int64_literal(loc, 48),
                            self._int64_binary(
                                '__mod__', value, self._int64_literal(loc, 10), loc
                            ),
                            loc,
                        ),
                        self._int64_binary('__add__', digits, position, loc),
                    ),
                    assign(
                        value,
                        self._int64_binary(
                            '__floordiv__', value, self._int64_literal(loc, 10), loc
                        ),
                    ),
                ]

            render = hir.Block(
                loc,
                ty.VOID_TYPE,
                [
                    hir.Flow(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.IfArm(
                                loc,
                                ty.VOID_TYPE,
                                negative,
                                assign(
                                    value,
                                    self._int64_binary(
                                        '__sub__',
                                        self._int64_literal(loc, 0),
                                        value,
                                        loc,
                                    ),
                                ),
                            )
                        ],
                        None,
                    ),
                    *emit_digit(),
                    hir.Flow(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.LoopArm(
                                loc,
                                ty.VOID_TYPE,
                                self._int64_comparison(
                                    '__lt__',
                                    self._int64_literal(loc, 0),
                                    value,
                                    loc,
                                ),
                                hir.Block(loc, ty.VOID_TYPE, emit_digit(), True),
                            )
                        ],
                        None,
                    ),
                    hir.Flow(
                        loc,
                        ty.VOID_TYPE,
                        [
                            hir.IfArm(
                                loc,
                                ty.VOID_TYPE,
                                negative,
                                hir.Block(
                                    loc,
                                    ty.VOID_TYPE,
                                    [
                                        assign(
                                            position,
                                            self._int64_binary(
                                                '__sub__',
                                                position,
                                                self._int64_literal(loc, 1),
                                                loc,
                                            ),
                                        ),
                                        store_digit(
                                            self._int64_literal(loc, 45),
                                            self._int64_binary(
                                                '__add__', digits, position, loc
                                            ),
                                        ),
                                    ],
                                    True,
                                ),
                            )
                        ],
                        None,
                    ),
                    assign(
                        source,
                        self._int64_binary('__add__', digits, position, loc),
                    ),
                    assign(
                        length,
                        self._int64_binary(
                            '__sub__',
                            self._int64_literal(loc, 20),
                            position,
                            loc,
                        ),
                    ),
                ],
                True,
            )
            # Negating the minimum value would overflow; use its literal text.
            statements.append(
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            loc,
                            ty.VOID_TYPE,
                            self._int64_comparison(
                                '__eq__',
                                value,
                                self._int64_literal(loc, -9223372036854775808),
                                loc,
                            ),
                            hir.Block(
                                loc,
                                ty.VOID_TYPE,
                                [
                                    assign(
                                        source,
                                        self._string_data_start(minimum_text, loc),
                                    ),
                                    assign(length, self._int64_literal(loc, 20)),
                                ],
                                True,
                            ),
                        )
                    ],
                    render,
                )
            )
            pieces.append((length, source))

        for part in node.parts:
            part_type = part.type
            if isinstance(part_type, ty.IntegerLiteralType):
                string_piece(
                    hir.String(
                        part.loc,
                        ty.StringLiteralType(str(part_type.value)),
                        str(part_type.value),
                    )
                )
            elif isinstance(part_type, (ty.StringLiteralType, ty.StringType)) or (
                isinstance(part_type, str)
                and part_type in {'string', 'grapheme', 'char'}
            ):
                string_piece(part)
            elif part_type == 'bool':
                bool_piece(part)
            elif isinstance(part_type, str) and (
                part_type == 'int' or part_type in FIXED_INTEGER_WIDTHS
            ):
                integer_piece(part)
            else:
                self._target_error(
                    part,
                    'materializing an interpolation field of type '
                    f'`{type_to_dewy(part_type)}`',
                )

        total = declare('byte_length', 'int64', self._int64_literal(loc, 0))
        for length, _source in pieces:
            statements.append(
                assign(total, self._int64_binary('__add__', total, length, loc))
            )
        dest_word = replace(dest, type='int64') if dest is not None else None
        data = declare(
            'data',
            'int64',
            self._load_i64_field(dest_word, STRING_DATA_OFFSET, loc)
            if dest_word is not None
            else self._intrinsic_call(
                allocator,
                [
                    self._int64_literal(loc, static_capacity + 1)
                    if static_capacity is not None
                    else self._int64_binary(
                        '__add__', total, self._int64_literal(loc, 1), loc
                    )
                ],
                'int64',
                loc,
            ),
        )
        cursor = declare('cursor', 'int64', self._int64_literal(loc, 0))
        for length, source in pieces:
            index = declare('copy_index', 'int64', self._int64_literal(loc, 0))
            statements.append(
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [
                        hir.LoopArm(
                            loc,
                            ty.VOID_TYPE,
                            self._int64_comparison('__lt__', index, length, loc),
                            hir.Block(
                                loc,
                                ty.VOID_TYPE,
                                [
                                    self._intrinsic_call(
                                        '__store_u8__',
                                        [
                                            self._intrinsic_call(
                                                '__load_u8__',
                                                [
                                                    self._int64_binary(
                                                        '__add__', source, index, loc
                                                    )
                                                ],
                                                'uint8',
                                                loc,
                                            ),
                                            self._int64_binary(
                                                '__add__',
                                                self._int64_binary(
                                                    '__add__', data, cursor, loc
                                                ),
                                                index,
                                                loc,
                                            ),
                                        ],
                                        ty.VOID_TYPE,
                                        loc,
                                    ),
                                    assign(
                                        index,
                                        self._int64_binary(
                                            '__add__',
                                            index,
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
            )
            statements.append(
                assign(cursor, self._int64_binary('__add__', cursor, length, loc))
            )
        boundaries = declare(
            'boundaries',
            'int64',
            self._load_i64_field(dest_word, STRING_BOUNDARIES_OFFSET, loc)
            if dest_word is not None
            else self._intrinsic_call(
                allocator,
                [
                    self._int64_literal(loc, (static_capacity + 1) * 4)
                    if static_capacity is not None
                    else self._int64_binary(
                        '__mul__',
                        self._int64_binary(
                            '__add__', total, self._int64_literal(loc, 1), loc
                        ),
                        self._int64_literal(loc, 4),
                        loc,
                    )
                ],
                'int64',
                loc,
            ),
        )
        segmentation, grapheme_count = self._utf8_segmentation(
            loc,
            data,
            total,
            boundaries,
        )
        statements.extend(segmentation)
        if dest is not None and dest_word is not None:
            statements.extend([
                self._store_i64_field(
                    dest_word, STRING_BYTE_LENGTH_OFFSET, total, loc
                ),
                self._store_i64_field(
                    dest_word, STRING_GRAPHEME_LENGTH_OFFSET, grapheme_count, loc
                ),
                self._store_i64_field(
                    dest_word,
                    STRING_START_OFFSET,
                    self._int64_literal(loc, 0),
                    loc,
                ),
            ])
            return statements, dest
        descriptor = self._new_string_temp(loc, node.type)
        descriptor_word = replace(descriptor, type='int64')
        statements.extend([
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, STRING_DESCRIPTOR_SIZE)],
                    'int64',
                    loc,
                ),
            ),
            self._store_i64_field(descriptor_word, STRING_DATA_OFFSET, data, loc),
            self._store_i64_field(
                descriptor_word, STRING_BYTE_LENGTH_OFFSET, total, loc
            ),
            self._store_i64_field(
                descriptor_word, STRING_BOUNDARIES_OFFSET, boundaries, loc
            ),
            self._store_i64_field(
                descriptor_word, STRING_GRAPHEME_LENGTH_OFFSET, grapheme_count, loc
            ),
            self._store_i64_field(
                descriptor_word,
                STRING_START_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
        ])
        return statements, descriptor


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

    def _view_allocation(self, loc: Span) -> hir.AST:
        """Storage for one view descriptor: the arena when the prelude provides
        one, else a fresh frame allocation per evaluation (a prelude-less
        program has no growable arrays for a view to escape into)."""
        has_arena = any(candidate.logical_name.endswith('_arena_alloc') for candidate in self.functions)
        size = self._int64_literal(loc, STRING_DESCRIPTOR_SIZE)
        if has_arena:
            return self._arena_allocation(size, loc)
        return self._intrinsic_call('__static_alloca__' if self.lowering_module_startup else '__alloca__', [size], 'int64', loc)

    def _string_view(
        self,
        string: hir.AST,
        first: hir.AST,
        count: hir.AST,
        type_: ty.Type,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        # A view's descriptor lives in the arena: a slice or indexed grapheme
        # can escape (pushed into an array, returned, stored in a field), and
        # a static cell would be shared by every evaluation in a loop — each
        # push of `text[start..stop]` would alias the last.
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
                self._view_allocation(loc),
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

