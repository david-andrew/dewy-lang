"""Dictionary lowering: a compact hash table over insertion-ordered entries.

The dictionary object is ``[keys values hashes indices live]``:

- ``keys``/``values``/``hashes`` are the dense *entries* in insertion order;
  ``hashes[i]`` is the entry's stored hash (never recomputed on resize) or
  ``-1`` for an entry removed by ``pop`` (a tombstone).
- ``indices`` is the sparse probe table: a power of two of ``int64`` slots
  holding ``-1`` (empty), ``-2`` (dummy: a removed entry once lived here,
  probing continues) or an entry index. Probing is CPython's
  ``i = (5*i + perturb + 1) mod size`` with ``perturb >>= 5``, ``perturb``
  starting as the hash. The table is (re)built lazily and kept under 2/3
  load counting tombstones; rebuilding compacts the entries.
- ``live`` counts entries that are not tombstones (``d.length``).

Hashes are the low 63 bits of a multiplicative mix for word keys and FNV-1a
over UTF-8 bytes for strings.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ...reporting import Span
from ...semantic import hir, ty
from .lowering_shared import ARRAY_LENGTH_OFFSET, STRING_BYTE_LENGTH_OFFSET

EMPTY = -1
DUMMY = -2
DEAD = -1
MIN_TABLE = 8
HASH_MASK = (1 << 63) - 1
WORD_MIX = 0x9E3779B97F4A7C15


@dataclass
class _DictParts:
    """Lowered access to one dictionary object."""

    pointer: hir.AST
    offsets: dict[str, int]
    object_type: ty.ObjectType
    key_type: ty.TypeExpr
    value_type: ty.TypeExpr | None
    """None for a set."""


class _DictLowering:
    # ------------------------------------------------------------------ parts
    def _dict_parts(self, keys: hir.AST) -> tuple[list[hir.AST], _DictParts]:
        """The dictionary object behind a `keys` member route of a dict node."""
        if not isinstance(keys, hir.MemberAccess):
            raise TypeError('INTERNAL ERROR: dictionary node without a member route')
        dictionary = keys.value
        object_type = dictionary.type
        entry_types = ty.container_entry_types(object_type) if isinstance(object_type, ty.ObjectType) else None
        if not isinstance(object_type, ty.ObjectType) or entry_types is None:
            raise TypeError('INTERNAL ERROR: dictionary node on a non-container')
        key_type, value_type = entry_types
        prelude, pointer = self._extract_object_pointer(dictionary)
        name = hir.ExpressedIdentifier(keys.loc, 'int64', self._new_array_name('dict'))
        _size, offsets = self._object_layout(object_type, dictionary)
        return [*prelude, hir.Declare(keys.loc, ty.VOID_TYPE, 'let', name.name, 'int64', pointer)], _DictParts(name, offsets, object_type, key_type, value_type)

    def _dict_descriptor(self, parts: _DictParts, field: str, loc: Span) -> hir.AST:
        return self._load_i64_field(parts.pointer, parts.offsets[field], loc)

    def _dict_live(self, parts: _DictParts, loc: Span) -> hir.AST:
        return self._load_i64_field(parts.pointer, parts.offsets['live'], loc)

    def _dict_set_live(self, parts: _DictParts, value: hir.AST, loc: Span) -> hir.AST:
        return self._store_i64_field(parts.pointer, parts.offsets['live'], value, loc)

    def _dict_length_of(self, descriptor: hir.AST, loc: Span) -> hir.AST:
        return self._load_i64_field(descriptor, ARRAY_LENGTH_OFFSET, loc)

    def _dict_element(self, descriptor: hir.AST, index: hir.AST, element: ty.TypeExpr, loc: Span) -> hir.AST:
        return self._array_load(self._array_element_address(descriptor, index, element, loc), element, loc)

    def _dict_store_element(self, descriptor: hir.AST, index: hir.AST, value: hir.AST, element: ty.TypeExpr, loc: Span) -> hir.AST:
        return self._array_store(value, self._array_element_address(descriptor, index, element, loc), element, loc)

    def _dict_push(self, parts: _DictParts, field: str, element: ty.TypeExpr, value: hir.AST, loc: Span) -> list[hir.AST]:
        member = hir.MemberAccess(loc, ty.ArrayType(element, None), self._dict_object_node(parts, loc), field)
        method = hir.ArrayMethod(loc, ty.FunctionType([ty.PosOrKwArg('value', element)], [], None, ty.VOID_TYPE), member, 'push')
        prelude, call = self._extract_array_method_call(hir.FunctionCall(loc, ty.VOID_TYPE, method, [value], {}))
        return [*prelude, call]

    def _dict_truncate(self, parts: _DictParts, field: str, element: ty.TypeExpr, count: hir.AST, loc: Span) -> list[hir.AST]:
        member = hir.MemberAccess(loc, ty.ArrayType(element, None), self._dict_object_node(parts, loc), field)
        method = hir.ArrayMethod(loc, ty.FunctionType([ty.PosOrKwArg('count', 'int64')], [], None, ty.VOID_TYPE), member, 'truncate')
        prelude, call = self._extract_array_method_call(hir.FunctionCall(loc, ty.VOID_TYPE, method, [count], {}))
        return [*prelude, call]

    def _dict_object_node(self, parts: _DictParts, loc: Span) -> hir.AST:
        """The dictionary as an object-typed expression for member routes (already a pointer)."""
        return replace(parts.pointer, type=parts.object_type)

    # ------------------------------------------------------------------ words
    def _word(self, name: str, left: hir.AST, right: hir.AST, loc: Span) -> hir.FunctionCall:
        ops = ty.FunctionType([ty.PosOrKwArg('left', 'uint64'), ty.PosOrKwArg('right', 'uint64')], [], None, 'uint64', [])
        return hir.FunctionCall(loc, 'uint64', hir.ExpressedIdentifier(loc, ops, name), [left, right], {})

    def _uword(self, value: int, loc: Span) -> hir.Integer:
        return hir.Integer(loc, 'uint64', '0d', value)

    def _declare(self, name: hir.ExpressedIdentifier, value: hir.AST, loc: Span, type_: ty.Type = 'int64') -> hir.Declare:
        return hir.Declare(loc, ty.VOID_TYPE, 'let', name.name, type_, value)

    def _assign(self, name: hir.ExpressedIdentifier, value: hir.AST, loc: Span) -> hir.Assign:
        return hir.Assign(loc, ty.VOID_TYPE, name, '=', value)

    def _name(self, role: str, loc: Span, type_: ty.Type = 'int64') -> hir.ExpressedIdentifier:
        return hir.ExpressedIdentifier(loc, type_, self._new_array_name(role))

    def _while(self, condition: hir.AST, body: list[hir.AST], loc: Span) -> hir.Flow:
        return hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(loc, ty.VOID_TYPE, condition, hir.Block(loc, ty.VOID_TYPE, body, True))], None)

    def _if(self, condition: hir.AST, body: list[hir.AST], loc: Span, otherwise: list[hir.AST] | None = None) -> hir.Flow:
        return hir.Flow(
            loc, ty.VOID_TYPE,
            [hir.IfArm(loc, ty.VOID_TYPE, condition, hir.Block(loc, ty.VOID_TYPE, body, True))],
            hir.Block(loc, ty.VOID_TYPE, otherwise, True) if otherwise is not None else None,
        )

    def _counting(self, role: str, limit: hir.AST, body_of, loc: Span) -> list[hir.AST]:
        counter = self._name(role, loc)
        one = self._int64_literal(loc, 1)
        return [
            self._declare(counter, self._int64_literal(loc, 0), loc),
            self._while(
                self._int64_comparison('__lt__', counter, limit, loc),
                [*body_of(counter), self._assign(counter, self._int64_binary('__add__', counter, one, loc), loc)],
                loc,
            ),
        ]

    # ------------------------------------------------------------------ hashing
    def _dict_hash(self, key: hir.AST, key_type: ty.TypeExpr, loc: Span) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """A non-negative int64 hash of a word or string key."""
        result = self._name('dict_hash', loc)
        if self._is_string_valued(key_type):
            # FNV-1a over the UTF-8 bytes
            accumulator = self._name('dict_fnv', loc, 'uint64')
            byte_count = self._load_i64_field(key, STRING_BYTE_LENGTH_OFFSET, loc)
            data = self._string_data_start(key, loc)
            statements: list[hir.AST] = [self._declare(accumulator, self._uword(0xCBF29CE484222325, loc), loc, 'uint64')]

            def step(index: hir.ExpressedIdentifier) -> list[hir.AST]:
                byte = self._intrinsic_call('__load_u8__', [self._int64_binary('__add__', data, index, loc)], 'uint8', loc)
                widened = hir.Transmute(loc, 'uint64', byte)
                mixed = self._word('__mul__', self._word('__xor__', accumulator, widened, loc), self._uword(0x100000001B3, loc), loc)
                return [self._assign(accumulator, mixed, loc)]

            statements.extend(self._counting('dict_byte', byte_count, step, loc))
            masked = self._word('__and__', accumulator, self._uword(HASH_MASK, loc), loc)
            statements.append(self._declare(result, hir.Transmute(loc, 'int64', masked), loc))
            return statements, result
        word = hir.Transmute(loc, 'uint64', key)
        mixed = self._word('__mul__', word, self._uword(WORD_MIX, loc), loc)
        folded = self._word('__xor__', mixed, self._word('__rshift__', mixed, self._uword(29, loc), loc), loc)
        masked = self._word('__and__', folded, self._uword(HASH_MASK, loc), loc)
        return [self._declare(result, hir.Transmute(loc, 'int64', masked), loc)], result

    # ------------------------------------------------------------------ table
    def _dict_rebuild(self, parts: _DictParts, capacity: hir.AST, loc: Span) -> list[hir.AST]:
        """Compact the entries (dropping tombstones), fill missing hashes, and build a fresh table."""
        keys = self._dict_descriptor(parts, 'keys', loc)
        values = self._dict_descriptor(parts, 'values', loc) if parts.value_type is not None else None
        hashes = self._dict_descriptor(parts, 'hashes', loc)
        indices = self._dict_descriptor(parts, 'indices', loc)
        entry_count = self._dict_length_of(keys, loc)
        hash_count = self._dict_length_of(hashes, loc)
        writer = self._name('dict_write', loc)
        statements: list[hir.AST] = [self._declare(writer, self._int64_literal(loc, 0), loc)]

        # 1. compact: keep entries whose hash is not DEAD (entries without a
        #    hash yet are live)
        def compact(reader: hir.ExpressedIdentifier) -> list[hir.AST]:
            has_hash = self._int64_comparison('__lt__', reader, hash_count, loc)
            dead = hir.ShortCircuit(
                loc, 'bool', 'and', has_hash,
                self._typed_equality(self._dict_element(hashes, reader, 'int64', loc), self._int64_literal(loc, DEAD), 'int64', loc),
            )
            moved = self._int64_comparison('__lt__', writer, reader, loc)
            copy = [
                self._dict_store_element(keys, writer, self._dict_element(keys, reader, parts.key_type, loc), parts.key_type, loc),
                *([self._dict_store_element(values, writer, self._dict_element(values, reader, parts.value_type, loc), parts.value_type, loc)]
                  if values is not None and parts.value_type is not None else []),
                self._if(has_hash, [self._dict_store_element(hashes, writer, self._dict_element(hashes, reader, 'int64', loc), 'int64', loc)], loc),
            ]
            return [self._if(dead, [], loc, [
                self._if(moved, copy, loc),
                self._assign(writer, self._int64_binary('__add__', writer, self._int64_literal(loc, 1), loc), loc),
            ])]

        statements.extend(self._counting('dict_read', entry_count, compact, loc))
        statements.extend(self._dict_truncate(parts, 'keys', parts.key_type, writer, loc))
        if parts.value_type is not None:
            statements.extend(self._dict_truncate(parts, 'values', parts.value_type, writer, loc))
        statements.extend(self._dict_truncate(parts, 'hashes', 'int64', writer, loc))
        statements.append(self._dict_set_live(parts, writer, loc))

        # 2. hashes for entries that never had one (a fresh literal)
        missing = self._name('dict_unhashed', loc)
        hash_prelude, hashed = self._dict_hash(self._dict_element(keys, missing, parts.key_type, loc), parts.key_type, loc)
        statements.append(self._declare(missing, self._dict_length_of(hashes, loc), loc))
        statements.append(self._while(
            self._int64_comparison('__lt__', missing, self._dict_length_of(keys, loc), loc),
            [*hash_prelude, *self._dict_push(parts, 'hashes', 'int64', hashed, loc),
             self._assign(missing, self._int64_binary('__add__', missing, self._int64_literal(loc, 1), loc), loc)],
            loc,
        ))

        # 3. the table: `capacity` empty slots, then every entry inserted by its hash
        size = self._name('dict_size', loc)
        statements.append(self._declare(size, capacity, loc))
        statements.extend(self._dict_truncate(parts, 'indices', 'int64', self._int64_literal(loc, 0), loc))
        statements.extend(self._counting('dict_slot', size, lambda _slot: self._dict_push(parts, 'indices', 'int64', self._int64_literal(loc, EMPTY), loc), loc))
        mask = self._name('dict_mask', loc)
        statements.append(self._declare(mask, self._int64_binary('__sub__', size, self._int64_literal(loc, 1), loc), loc))

        def insert(entry: hir.ExpressedIdentifier) -> list[hir.AST]:
            entry_hash = self._dict_element(hashes, entry, 'int64', loc)
            slot = self._name('dict_i', loc)
            perturb = self._name('dict_perturb', loc, 'uint64')
            probe_step = self._probe_step(slot, perturb, mask, loc)
            occupied = hir.FunctionCall(
                loc, 'bool',
                hir.ExpressedIdentifier(loc, ty.FunctionType([ty.PosOrKwArg('l', 'int64'), ty.PosOrKwArg('r', 'int64')], [], None, 'bool', []), '__ne__'),
                [self._dict_element(indices, slot, 'int64', loc), self._int64_literal(loc, EMPTY)], {},
            )
            return [
                self._declare(slot, self._int64_binary('__and__', entry_hash, mask, loc), loc),
                self._declare(perturb, hir.Transmute(loc, 'uint64', entry_hash), loc, 'uint64'),
                self._while(occupied, probe_step, loc),
                self._dict_store_element(indices, slot, entry, 'int64', loc),
            ]

        statements.extend(self._counting('dict_entry', self._dict_length_of(keys, loc), insert, loc))
        return statements

    def _probe_step(self, slot: hir.ExpressedIdentifier, perturb: hir.ExpressedIdentifier, mask: hir.AST, loc: Span) -> list[hir.AST]:
        """`perturb >>= 5; i = (5*i + perturb + 1) & mask`."""
        return [
            self._assign(perturb, self._word('__rshift__', perturb, self._uword(5, loc), loc), loc),
            self._assign(slot, self._int64_binary(
                '__and__',
                self._int64_binary(
                    '__add__',
                    self._int64_binary('__add__', self._int64_binary('__mul__', self._int64_literal(loc, 5), slot, loc), hir.Transmute(loc, 'int64', perturb), loc),
                    self._int64_literal(loc, 1), loc,
                ),
                mask, loc,
            ), loc),
        ]

    def _table_capacity_for(self, entries: hir.AST, loc: Span) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """The smallest power of two of at least MIN_TABLE keeping `entries` under 2/3 load."""
        capacity = self._name('dict_capacity', loc)
        needed = self._int64_binary('__mul__', entries, self._int64_literal(loc, 3), loc)
        return [
            self._declare(capacity, self._int64_literal(loc, MIN_TABLE), loc),
            self._while(
                self._int64_comparison('__le__', self._int64_binary('__mul__', capacity, self._int64_literal(loc, 2), loc), needed, loc),
                [self._assign(capacity, self._int64_binary('__mul__', capacity, self._int64_literal(loc, 2), loc), loc)],
                loc,
            ),
        ], capacity

    def _dict_ensure_table(self, parts: _DictParts, loc: Span, *, room_for: int = 0) -> list[hir.AST]:
        """Build the table on first use, or rebuild when `room_for` more entries would exceed 2/3 load."""
        indices = self._dict_descriptor(parts, 'indices', loc)
        keys = self._dict_descriptor(parts, 'keys', loc)
        entries = self._int64_binary('__add__', self._dict_length_of(keys, loc), self._int64_literal(loc, room_for), loc)
        capacity_prelude, capacity = self._table_capacity_for(self._int64_binary('__add__', self._dict_live(parts, loc), self._int64_literal(loc, room_for), loc), loc)
        too_full = self._int64_comparison(
            '__gt__',
            self._int64_binary('__mul__', entries, self._int64_literal(loc, 3), loc),
            self._int64_binary('__mul__', self._dict_length_of(indices, loc), self._int64_literal(loc, 2), loc),
            loc,
        )
        return [self._if(too_full, [*capacity_prelude, *self._dict_rebuild(parts, capacity, loc)], loc)]

    def _dict_probe(
        self,
        parts: _DictParts,
        key: hir.AST,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier, hir.ExpressedIdentifier, hir.ExpressedIdentifier]:
        """Search for `key`: (statements, found, entry position, table slot).

        The slot is the entry's slot when found, else the first dummy or the
        empty slot that ended the probe — where an insertion goes.
        """
        keys = self._dict_descriptor(parts, 'keys', loc)
        hashes = self._dict_descriptor(parts, 'hashes', loc)
        indices = self._dict_descriptor(parts, 'indices', loc)
        hash_prelude, key_hash = self._dict_hash(key, parts.key_type, loc)
        found = self._name('dict_found', loc, 'bool')
        position = self._name('dict_pos', loc)
        slot = self._name('dict_slot', loc)
        cursor = self._name('dict_i', loc)
        perturb = self._name('dict_perturb', loc, 'uint64')
        searching = self._name('dict_searching', loc, 'bool')
        mask = self._name('dict_mask', loc)
        entry = self._name('dict_entry', loc)
        entry_key = self._dict_element(keys, entry, parts.key_type, loc)
        if self._is_string_valued(parts.key_type):
            equal_prelude, keys_equal = self._extract_string_equal(hir.StringEqual(loc, 'bool', entry_key, key))
        else:
            equal_prelude, keys_equal = [], self._typed_equality(entry_key, key, parts.key_type, loc)
        same_hash = self._typed_equality(self._dict_element(hashes, entry, 'int64', loc), key_hash, 'int64', loc)
        remember_slot = self._if(self._int64_comparison('__lt__', slot, self._int64_literal(loc, 0), loc), [self._assign(slot, cursor, loc)], loc)
        body = [
            self._declare(entry, self._dict_element(indices, cursor, 'int64', loc), loc),
            self._if(
                self._typed_equality(entry, self._int64_literal(loc, EMPTY), 'int64', loc),
                [remember_slot, self._assign(searching, hir.Bool(loc, 'bool', False), loc)],
                loc,
                [self._if(
                    self._typed_equality(entry, self._int64_literal(loc, DUMMY), 'int64', loc),
                    [remember_slot, *self._probe_step(cursor, perturb, mask, loc)],
                    loc,
                    [*equal_prelude, self._if(
                        hir.ShortCircuit(loc, 'bool', 'and', same_hash, keys_equal),
                        [
                            self._assign(found, hir.Bool(loc, 'bool', True), loc),
                            self._assign(position, entry, loc),
                            self._assign(slot, cursor, loc),
                            self._assign(searching, hir.Bool(loc, 'bool', False), loc),
                        ],
                        loc,
                        self._probe_step(cursor, perturb, mask, loc),
                    )],
                )],
            ),
        ]
        statements: list[hir.AST] = [
            *hash_prelude,
            self._declare(found, hir.Bool(loc, 'bool', False), loc, 'bool'),
            self._declare(position, self._int64_literal(loc, -1), loc),
            self._declare(slot, self._int64_literal(loc, -1), loc),
            self._declare(mask, self._int64_binary('__sub__', self._dict_length_of(indices, loc), self._int64_literal(loc, 1), loc), loc),
            self._declare(cursor, self._int64_binary('__and__', key_hash, mask, loc), loc),
            self._declare(perturb, hir.Transmute(loc, 'uint64', key_hash), loc, 'uint64'),
            self._declare(searching, hir.Bool(loc, 'bool', True), loc, 'bool'),
            self._while(searching, body, loc),
        ]
        return statements, found, position, slot

    # ------------------------------------------------------------------ nodes
    def _extract_dict_lookup(self, node: hir.DictLookup) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        prelude, parts = self._dict_parts(node.keys)
        key_prelude, key = self._extract_expression(node.key)
        values = self._dict_descriptor(parts, 'values', loc)

        def value_at(index: hir.AST) -> hir.AST:
            return self._dict_element(values, index, parts.value_type, loc)

        if node.proven:
            if node.static_position is not None:
                search: list[hir.AST] = []
                position: hir.AST = self._int64_literal(loc, node.static_position)
            elif node.position is not None:
                search = []
                position = hir.ExpressedIdentifier(loc, 'int64', node.position)
            else:
                search = [*self._dict_ensure_table(parts, loc)]
                probe, _found, position, _slot = self._dict_probe(parts, key, loc)
                search.extend(probe)
            result = self._name('dict_value', loc, parts.value_type)
            return [*prelude, *key_prelude, *search, self._declare(result, value_at(position), loc, parts.value_type)], result
        search = [*self._dict_ensure_table(parts, loc)]
        probe, found, position, _slot = self._dict_probe(parts, key, loc)
        search.extend(probe)
        if node.default is not None:
            default_prelude, default = self._extract_expression(node.default)
            result = self._name('dict_value', loc, parts.value_type)
            return [
                *prelude, *key_prelude, *default_prelude, *search,
                self._declare(result, default, loc, parts.value_type),
                self._if(found, [self._assign(result, value_at(position), loc)], loc),
            ], result
        payload = ty.optional_payload(node.type)
        if payload is None:
            raise TypeError('INTERNAL ERROR: dictionary lookup is not optional')
        cell = hir.ExpressedIdentifier(loc, node.type, self._new_optional_name('dict_value'))
        cell_word = replace(cell, type='int64')
        return [
            *prelude, *key_prelude, *search,
            hir.Declare(loc, ty.VOID_TYPE, 'let', cell.name, 'int64', self._optional_allocation(loc)),
            *self._optional_write(cell_word, hir.Undefined(loc, 'undefined'), payload),
            self._if(found, self._optional_write(cell_word, value_at(position), payload), loc),
        ], cell

    def _extract_dict_contains(self, node: hir.DictContains) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        prelude, parts = self._dict_parts(node.keys)
        key_prelude, key = self._extract_expression(node.key)
        ensure = self._dict_ensure_table(parts, loc)
        probe, found, position, _slot = self._dict_probe(parts, key, loc)
        remembered: list[hir.AST] = []
        if node.position is not None:
            remembered.append(hir.Declare(loc, ty.VOID_TYPE, 'let', node.position, 'int64', position))
        return [*prelude, *key_prelude, *ensure, *probe, *remembered], found

    def _extract_dict_store(self, node: hir.DictStore) -> tuple[list[hir.AST], hir.AST]:
        loc = node.loc
        prelude, parts = self._dict_parts(node.keys)
        key_prelude, key = self._extract_expression(node.key)
        value_prelude, value = self._extract_expression(node.value) if node.value is not None else ([], None)
        values = self._dict_descriptor(parts, 'values', loc) if parts.value_type is not None else None
        keys = self._dict_descriptor(parts, 'keys', loc)
        indices = self._dict_descriptor(parts, 'indices', loc)
        ensure = self._dict_ensure_table(parts, loc, room_for=1)
        probe, found, position, slot = self._dict_probe(parts, key, loc)
        hash_prelude, key_hash = self._dict_hash(key, parts.key_type, loc)
        new_position = self._name('dict_new', loc)
        remembered: list[hir.AST] = []
        if node.position is not None:
            remembered.append(hir.Declare(loc, ty.VOID_TYPE, 'let', node.position, 'int64', position))
        replace_value = (
            [self._dict_store_element(values, position, value, parts.value_type, loc)]
            if values is not None and value is not None and parts.value_type is not None
            else []
        )
        append = [
            self._declare(new_position, self._dict_length_of(keys, loc), loc),
            *self._dict_push(parts, 'keys', parts.key_type, key, loc),
            *(self._dict_push(parts, 'values', parts.value_type, value, loc) if value is not None and parts.value_type is not None else []),
            *hash_prelude,
            *self._dict_push(parts, 'hashes', 'int64', key_hash, loc),
            self._dict_store_element(indices, slot, new_position, 'int64', loc),
            self._dict_set_live(parts, self._int64_binary('__add__', self._dict_live(parts, loc), self._int64_literal(loc, 1), loc), loc),
            *([hir.Assign(loc, ty.VOID_TYPE, hir.ExpressedIdentifier(loc, 'int64', node.position), '=', new_position)] if node.position is not None else []),
        ]
        return [
            *prelude, *key_prelude, *value_prelude, *ensure, *probe, *remembered,
            self._if(found, replace_value, loc, append),
        ], hir.Void(loc, ty.VOID_TYPE)

    def _extract_dict_remove(self, node: hir.DictRemove) -> tuple[list[hir.AST], hir.AST]:
        """`d.pop(key)` tombstones the entry; `d.clear` empties everything."""
        loc = node.loc
        prelude, parts = self._dict_parts(node.keys)
        if node.key is None:
            statements: list[hir.AST] = [*prelude]
            fields: list[tuple[str, ty.TypeExpr]] = [('keys', parts.key_type)]
            if parts.value_type is not None:
                fields.append(('values', parts.value_type))
            fields.extend([('hashes', 'int64'), ('indices', 'int64')])
            for field, element in fields:
                statements.extend(self._dict_truncate(parts, field, element, self._int64_literal(loc, 0), loc))
            statements.append(self._dict_set_live(parts, self._int64_literal(loc, 0), loc))
            return statements, hir.Void(loc, ty.VOID_TYPE)
        key_prelude, key = self._extract_expression(node.key)
        hashes = self._dict_descriptor(parts, 'hashes', loc)
        indices = self._dict_descriptor(parts, 'indices', loc)
        # a remembered position still needs the slot: probing by key finds
        # both (a proven key's probe succeeds)
        ensure = self._dict_ensure_table(parts, loc)
        probe, found, position, slot = self._dict_probe(parts, key, loc)
        tombstone = [
            self._dict_store_element(hashes, position, self._int64_literal(loc, DEAD), 'int64', loc),
            self._dict_store_element(indices, slot, self._int64_literal(loc, DUMMY), 'int64', loc),
            self._dict_set_live(parts, self._int64_binary('__sub__', self._dict_live(parts, loc), self._int64_literal(loc, 1), loc), loc),
        ]
        if parts.value_type is None:
            # a set: `pop(x)` (proven) yields the member; `pop(x default=v)`
            # yields the member when present (removing it) else `v`
            if not node.lenient:
                return [*prelude, *key_prelude, *ensure, *probe, *tombstone], key
            assert node.default is not None
            payload = ty.optional_payload(node.type)
            if payload is not None:
                # `default=undefined`: an optional cell, undefined unless the member was present
                cell = hir.ExpressedIdentifier(loc, node.type, self._new_optional_name('set_popped'))
                cell_word = replace(cell, type='int64')
                return [
                    *prelude, *key_prelude, *ensure, *probe,
                    hir.Declare(loc, ty.VOID_TYPE, 'let', cell.name, 'int64', self._optional_allocation(loc)),
                    *self._optional_write(cell_word, hir.Undefined(loc, 'undefined'), payload),
                    self._if(found, [*self._optional_write(cell_word, key, payload), *tombstone], loc),
                ], cell
            default_prelude, default = self._extract_expression(node.default)
            popped = self._name('set_popped', loc, parts.key_type)
            return [
                *prelude, *key_prelude, *default_prelude, *ensure, *probe,
                self._declare(popped, default, loc, parts.key_type),
                self._if(found, [self._assign(popped, key, loc), *tombstone], loc),
            ], popped
        values = self._dict_descriptor(parts, 'values', loc)
        removed = self._name('dict_removed', loc, parts.value_type)
        if node.default is None:
            # proven present: the probe succeeds
            return [
                *prelude, *key_prelude, *ensure, *probe,
                self._declare(removed, self._dict_element(values, position, parts.value_type, loc), loc, parts.value_type),
                *tombstone,
            ], removed
        default_prelude, default = self._extract_expression(node.default)
        return [
            *prelude, *key_prelude, *default_prelude, *ensure, *probe,
            self._declare(removed, default, loc, parts.value_type),
            self._if(found, [self._assign(removed, self._dict_element(values, position, parts.value_type, loc), loc), *tombstone], loc),
        ], removed

    def _extract_dict_entries(self, node: hir.DictEntries) -> tuple[list[hir.AST], hir.AST]:
        """The entry array for iteration, compacted first if removals left tombstones."""
        loc = node.loc
        member = hir.MemberAccess(loc, node.type, node.dictionary, 'keys')
        prelude, parts = self._dict_parts(member)
        keys = self._dict_descriptor(parts, 'keys', loc)
        has_dead = self._int64_comparison('__gt__', self._dict_length_of(keys, loc), self._dict_live(parts, loc), loc)
        capacity_prelude, capacity = self._table_capacity_for(self._dict_live(parts, loc), loc)
        compact = self._if(has_dead, [*capacity_prelude, *self._dict_rebuild(parts, capacity, loc)], loc)
        return [*prelude, compact], self._dict_descriptor(parts, node.name, loc)

    def _extract_set_algebra(self, node: hir.SetAlgebra) -> tuple[list[hir.AST], hir.AST]:
        """Build a new set from two: union, intersection, difference, symmetric difference."""
        loc = node.loc
        element = ty.set_element(node.type)
        assert element is not None
        set_type = ty.set_type(element)
        empty = hir.ObjectLiteral(loc, set_type, [
            hir.ObjectField(loc, 'keys', hir.ArrayLiteral(loc, ty.ArrayType(element, 0), [])),
            hir.ObjectField(loc, 'hashes', hir.ArrayLiteral(loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(loc, 'indices', hir.ArrayLiteral(loc, ty.ArrayType('int64', 0), [])),
            hir.ObjectField(loc, 'live', hir.Integer(loc, 'int64', '0d', 0)),
        ])
        result_prelude, result_pointer = self._extract_object_pointer(empty)
        result_name = self._name('set_result', loc)
        result_object = replace(result_name, type=set_type)
        left_prelude, left = self._dict_parts(hir.MemberAccess(loc, ty.ArrayType(element, None), node.left, 'keys'))
        right_prelude, right = self._dict_parts(hir.MemberAccess(loc, ty.ArrayType(element, None), node.right, 'keys'))
        statements: list[hir.AST] = [
            *result_prelude,
            self._declare(result_name, result_pointer, loc),
            *left_prelude,
            *right_prelude,
            *self._dict_ensure_table(left, loc),
            *self._dict_ensure_table(right, loc),
        ]

        def add_members(source: _DictParts, other: _DictParts | None, *, when_found: bool) -> list[hir.AST]:
            """Add each live member of `source` (filtered by membership in `other`) to the result."""
            keys = self._dict_descriptor(source, 'keys', loc)
            hashes = self._dict_descriptor(source, 'hashes', loc)
            hash_count = self._dict_length_of(hashes, loc)

            def body(index: hir.ExpressedIdentifier) -> list[hir.AST]:
                member = self._name('set_member', loc, element)
                add_prelude, add = self._extract_dict_store(hir.DictStore(
                    loc, ty.VOID_TYPE,
                    hir.MemberAccess(loc, ty.ArrayType(element, None), result_object, 'keys'),
                    None, member, None,
                ))
                adding = [*add_prelude, add]
                if other is not None:
                    probe, found, _position, _slot = self._dict_probe(other, member, loc)
                    adding = [*probe, self._if(found, adding, loc) if when_found else self._if(found, [], loc, adding)]
                alive = hir.ShortCircuit(
                    loc, 'bool', 'or',
                    self._int64_comparison('__ge__', index, hash_count, loc),
                    hir.FunctionCall(
                        loc, 'bool',
                        hir.ExpressedIdentifier(loc, ty.FunctionType([ty.PosOrKwArg('l', 'int64'), ty.PosOrKwArg('r', 'int64')], [], None, 'bool', []), '__ne__'),
                        [self._dict_element(hashes, index, 'int64', loc), self._int64_literal(loc, DEAD)], {},
                    ),
                )
                return [
                    self._declare(member, self._dict_element(keys, index, element, loc), loc, element),
                    self._if(alive, adding, loc),
                ]

            return self._counting('set_index', self._dict_length_of(keys, loc), body, loc)

        if node.op == 'union':
            statements.extend(add_members(left, None, when_found=True))
            statements.extend(add_members(right, None, when_found=True))
        elif node.op == 'intersection':
            statements.extend(add_members(left, right, when_found=True))
        elif node.op == 'difference':
            statements.extend(add_members(left, right, when_found=False))
        else:  # symmetric difference
            statements.extend(add_members(left, right, when_found=False))
            statements.extend(add_members(right, left, when_found=False))
        return statements, result_name
