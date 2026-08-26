"""Dictionary lowering: linear search over the hidden key/value arrays.

Dictionaries are hidden parallel arrays (insertion order is entry order).
Lookup, store, and membership search the key array linearly; the compact
hash-index table from the reference design can replace the search later
without changing these semantics.
"""

from __future__ import annotations

from dataclasses import replace

from ...reporting import Span
from ...semantic import hir, ty
from .lowering_shared import ARRAY_LENGTH_OFFSET


class _DictLowering:
    def _dict_search(
        self,
        keys: hir.AST,
        key: hir.AST,
        key_type: ty.TypeExpr,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier, hir.ExpressedIdentifier]:
        """Emit a search for ``key``; returns (statements, found, index)."""
        found = hir.ExpressedIdentifier(loc, 'bool', self._new_array_name('dict_found'))
        at = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('dict_at'))
        index = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('dict_index'))
        length = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('dict_length'))
        keys_word = replace(keys, type='int64') if isinstance(keys, hir.ExpressedIdentifier) else keys
        element = self._array_load(
            self._array_element_address(keys_word, index, key_type, loc),
            key_type,
            loc,
        )
        if self._is_string_valued(key_type):
            equal_prelude, equal = self._extract_string_equal(
                hir.StringEqual(loc, 'bool', element, key)
            )
        else:
            equal_prelude, equal = [], self._typed_equality(element, key, key_type, loc)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.Assign:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        body = hir.Block(
            loc,
            ty.VOID_TYPE,
            [
                *equal_prelude,
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            loc,
                            ty.VOID_TYPE,
                            equal,
                            hir.Block(
                                loc,
                                ty.VOID_TYPE,
                                [
                                    assign(found, hir.Bool(loc, 'bool', True)),
                                    assign(at, index),
                                    assign(index, length),
                                ],
                                True,
                            ),
                        )
                    ],
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc))],
                        True,
                    ),
                ),
            ],
            True,
        )
        statements: list[hir.AST] = [
            hir.Declare(loc, ty.VOID_TYPE, 'let', found.name, 'bool', hir.Bool(loc, 'bool', False)),
            hir.Declare(loc, ty.VOID_TYPE, 'let', at.name, 'int64', self._int64_literal(loc, 0)),
            hir.Declare(loc, ty.VOID_TYPE, 'let', index.name, 'int64', self._int64_literal(loc, 0)),
            hir.Declare(
                loc, ty.VOID_TYPE, 'let', length.name, 'int64',
                self._load_i64_field(keys_word, ARRAY_LENGTH_OFFSET, loc),
            ),
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [hir.LoopArm(loc, ty.VOID_TYPE, self._int64_comparison('__lt__', index, length, loc), body)],
                None,
            ),
        ]
        return statements, found, at

    def _dict_types(self, keys: hir.AST, values: hir.AST) -> tuple[ty.TypeExpr, ty.TypeExpr]:
        if not isinstance(keys.type, ty.ArrayType) or not isinstance(values.type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: dictionary arrays are not arrays')
        return keys.type.element, values.type.element

    def _extract_dict_lookup(self, node: hir.DictLookup) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        key_type, value_type = self._dict_types(node.keys, node.values)
        keys_prelude, keys = self._extract_expression(node.keys)
        values_prelude, values = self._extract_expression(node.values)
        key_prelude, key = self._extract_expression(node.key)
        values_word = replace(values, type='int64') if isinstance(values, hir.ExpressedIdentifier) else values

        def value_at(index: hir.AST) -> hir.AST:
            return self._array_load(self._array_element_address(values_word, index, value_type, loc), value_type, loc)

        if node.proven:
            # the key is present: read it at the position a guard, store, or
            # the literal established, or search knowing the search succeeds
            if node.static_position is not None:
                position: hir.AST = self._int64_literal(loc, node.static_position)
                search: list[hir.AST] = []
            elif node.position is not None:
                position = hir.ExpressedIdentifier(loc, 'int64', node.position)
                search = []
            else:
                search, _found, position = self._dict_search(keys, key, key_type, loc)
            result = hir.ExpressedIdentifier(loc, value_type, self._new_array_name('dict_value'))
            return [
                *keys_prelude, *values_prelude, *key_prelude, *search,
                hir.Declare(loc, ty.VOID_TYPE, 'let', result.name, value_type, value_at(position)),
            ], result
        search, found, at = self._dict_search(keys, key, key_type, loc)
        if node.default is not None:
            # `d.get(key default)`: the default unless the key is found
            default_prelude, default = self._extract_expression(node.default)
            result = hir.ExpressedIdentifier(loc, value_type, self._new_array_name('dict_value'))
            return [
                *keys_prelude, *values_prelude, *key_prelude, *default_prelude, *search,
                hir.Declare(loc, ty.VOID_TYPE, 'let', result.name, value_type, default),
                hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                    loc, ty.VOID_TYPE, found,
                    hir.Block(loc, ty.VOID_TYPE, [hir.Assign(loc, ty.VOID_TYPE, result, '=', value_at(at))], True),
                )], None),
            ], result
        payload = ty.optional_payload(node.type)
        if payload is None:
            raise TypeError('INTERNAL ERROR: dictionary lookup is not optional')
        cell = hir.ExpressedIdentifier(loc, node.type, self._new_optional_name('dict_value'))
        cell_word = replace(cell, type='int64')
        statements: list[hir.AST] = [
            *keys_prelude,
            *values_prelude,
            *key_prelude,
            *search,
            hir.Declare(loc, ty.VOID_TYPE, 'let', cell.name, 'int64', self._optional_allocation(loc)),
            *self._optional_write(cell_word, hir.Undefined(loc, 'undefined'), payload),
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [
                    hir.IfArm(
                        loc,
                        ty.VOID_TYPE,
                        found,
                        hir.Block(loc, ty.VOID_TYPE, self._optional_write(cell_word, value_at(at), payload), True),
                    )
                ],
                None,
            ),
        ]
        return statements, cell

    def _extract_dict_contains(self, node: hir.DictContains) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        if not isinstance(node.keys.type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: dictionary keys are not an array')
        keys_prelude, keys = self._extract_expression(node.keys)
        key_prelude, key = self._extract_expression(node.key)
        search, found, at = self._dict_search(keys, key, node.keys.type.element, loc)
        position: list[hir.AST] = []
        if node.position is not None:
            # a guarded lookup reuses the search result
            position.append(hir.Declare(loc, ty.VOID_TYPE, 'let', node.position, 'int64', at))
        return [*keys_prelude, *key_prelude, *search, *position], found

    def _extract_dict_store(self, node: hir.DictStore) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        key_type, value_type = self._dict_types(node.keys, node.values)
        keys_prelude, keys = self._extract_expression(node.keys)
        values_prelude, values = self._extract_expression(node.values)
        key_prelude, key = self._extract_expression(node.key)
        value_prelude, value = self._extract_expression(node.value)
        search, found, at = self._dict_search(keys, key, key_type, loc)
        values_word = replace(values, type='int64') if isinstance(values, hir.ExpressedIdentifier) else values
        replace_value = self._array_store(
            value,
            self._array_element_address(values_word, at, value_type, loc),
            value_type,
            loc,
        )

        def push(array: hir.AST, item: hir.AST, element: ty.TypeExpr) -> list[hir.AST]:
            method = hir.ArrayMethod(
                loc,
                ty.FunctionType([ty.PosOrKwArg('value', element)], [], None, ty.VOID_TYPE),
                array,
                'push',
            )
            prelude, call = self._extract_array_method_call(
                hir.FunctionCall(loc, ty.VOID_TYPE, method, [item], {})
            )
            return [*prelude, call]

        position_statements: list[hir.AST] = []
        appended: list[hir.AST] = []
        if node.position is not None:
            # a following lookup of this key reads the entry directly: the
            # found index, or the index of the appended entry
            position = hir.ExpressedIdentifier(loc, 'int64', node.position)
            position_statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', position.name, 'int64', at))
            keys_word = replace(keys, type='int64') if isinstance(keys, hir.ExpressedIdentifier) else keys
            appended.append(hir.Assign(
                loc, ty.VOID_TYPE, position, '=',
                self._load_i64_field(keys_word, ARRAY_LENGTH_OFFSET, loc),
            ))
        statements: list[hir.AST] = [
            *keys_prelude,
            *values_prelude,
            *key_prelude,
            *value_prelude,
            *search,
            *position_statements,
            hir.Flow(
                loc,
                ty.VOID_TYPE,
                [hir.IfArm(loc, ty.VOID_TYPE, found, hir.Block(loc, ty.VOID_TYPE, [replace_value], True))],
                hir.Block(
                    loc,
                    ty.VOID_TYPE,
                    [*appended, *push(node.keys, key, key_type), *push(node.values, value, value_type)],
                    True,
                ),
            ),
        ]
        return statements, hir.Void(loc, ty.VOID_TYPE)
