"""Provisional copy-on-write backing storage; source values stay independent.

Descriptors remain private. Owner 0 denotes frame/static data, 1 uniquely
owned arena data, and, only with ARRAY_SHARED, an aligned pointer >1 a shared count.
Borrowed string views can instead keep their source string in owner.
Only arena data can be shared. Mutation detaches before exposing an element
place; final release visits the elements exactly once. See bootstrap/PERFORMANCE.md
for the open long-term predictability/zero-cost design question.
"""
from ...utils import dataclass_replace as replace

from ...semantic import hir, ty
from .lowering_shared import (
    ARRAY_ARENA_DESCRIPTOR,
    ARRAY_CAPACITY_OFFSET,
    ARRAY_DATA_OFFSET,
    ARRAY_DESCRIPTOR_SIZE,
    ARRAY_FLAGS_OFFSET,
    ARRAY_LENGTH_OFFSET,
    ARRAY_MUTABLE,
    ARRAY_OWNER_OFFSET,
    ARRAY_SHARED,
    ARRAY_STRIDE_OFFSET,
    STRING_DESCRIPTOR_SIZE,
    STRING_OWNER_OFFSET,
    STRING_BYTE_LENGTH_OFFSET,
)


class _ArraySharing:
    @staticmethod
    def _raw_memory_intrinsic_name(name):
        return name.startswith(('__load_', '__store_', '__syscall')) or name in {'__load__', '__store__'}

    def _raw_aggregate_intrinsic(self, node):
        callee = node.func
        if not isinstance(callee, hir.ExpressedIdentifier):
            return None
        if not self._raw_memory_intrinsic_name(callee.name):
            return None
        # Discovery distinguishes source intrinsics (known, unbound names)
        # from user functions and loads/stores synthesized by lowering. An
        # internal load may address inline fixed-array data, not a descriptor.
        if id(node) not in self.source_intrinsic_calls:
            return None
        if not any(self._pin_type(arg.type) for arg in node.pos_args):
            return None
        prefix, arguments = [], []
        for argument in node.pos_args:
            before, value = self._extract_expression(argument)
            prefix.extend(before)
            held = self._name('raw_argument', argument.loc)
            prefix.append(self._declare(held, replace(value, type='int64'), argument.loc))
            prefix.extend(self._pin_aggregate_call(held, argument.type, argument.loc))
            arguments.append(held)
        return prefix, self._intrinsic_call(callee.name, arguments, self._lower_runtime_value_type(node.type), node.loc)

    @staticmethod
    def _pin_type(type_):
        unfolded = ty.unfold(ty.strip_refinement(type_))
        return ty.string_valued(unfolded) or isinstance(unfolded, (ty.ArrayType, ty.ObjectType)) or ty.runtime_union_members(type_) is not None or ty.optional_payload(type_) is not None

    @staticmethod
    def _index_storage_type(node):
        array = ty.unfold(ty.strip_refinement(node.array.type))
        assert isinstance(array, ty.ArrayType)
        return array.element

    def _read_index_storage(self, address, node):
        # Narrowing changes the read type, never the element stride or its
        # tag/payload storage. This rule is shared by reads and mutable routes.
        stored = self._index_storage_type(node)
        value = self._array_load(address, stored, node.loc)
        members = self._field_union_members(stored)
        if members is not None:
            return self._union_field_read(value, members, node.type, node)
        return replace(value, type=node.type)

    def _extract_write_route(self, node):
        """Evaluate a nested place once, detaching enclosing array buffers."""
        if isinstance(node, hir.Index) and self._array_use_representation(node.array) is None:
            prelude, array = self._extract_write_route(node.array)
            before, index = self._extract_index_value(node.index, node.constant_index)
            prelude.extend(before)
            stored = self._index_storage_type(node)
            prelude.extend(self._ensure_unique_array(array, stored, node.loc))
            address = self._array_element_address(array, index, stored, node.loc)
            return prelude, self._read_index_storage(address, node)
        if isinstance(node, hir.MemberAccess):
            prelude, value = self._extract_write_route(node.value)
            base = self._name('write_object', node.loc)
            prelude.append(self._declare(base, replace(value, type='int64'), node.loc))
            before, result = self._extract_member_access(replace(node, value=replace(base, type=node.value.type)))
            return [*prelude, *before], result
        return self._extract_expression(node)

    def _array_is_shared(self, descriptor, owner, loc):
        flags = self._load_i64_field(descriptor, ARRAY_FLAGS_OFFSET, loc)
        tagged = self._int64_comparison('__ne__', self._int64_binary('__and__', flags, self._int64_literal(loc, ARRAY_SHARED), loc), self._int64_literal(loc, 0), loc)
        return hir.ShortCircuit(loc, 'bool', 'and', tagged, self._int64_comparison('__gt__', owner, self._int64_literal(loc, 1), loc))

    def _note_array_copy(self, size, loc):
        helper = self._runtime_helper('_arena_note_copy')
        if helper is None:
            return []
        signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
        return [hir.FunctionCall(loc, ty.VOID_TYPE, hir.ExpressedIdentifier(loc, signature, helper.symbol), [size], {})]

    def _shared_array_copy_call(self, source, array_type, loc):
        symbol = next((name for existing, name in self.shared_copy_symbols if existing == array_type), None)
        if symbol is None:
            symbol = self._internal_symbol(f'__dewy_copy_array_{len(self.shared_copy_symbols)}')
            self.shared_copy_symbols.append((array_type, symbol))
            self.pending_shared_copies.append((array_type, symbol))
        signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'int64')
        return hir.FunctionCall(loc, 'int64', hir.ExpressedIdentifier(loc, signature, symbol), [source], {})

    def _synthesize_shared_copies(self):
        from .lowering_shared import LoweredFunction
        result = []
        while self.pending_shared_copies:
            array_type, symbol = self.pending_shared_copies.pop(0)
            loc = self.root.loc
            source = hir.ExpressedIdentifier(loc, array_type, '__dewy_array_source')
            prefix, value = self._clone_dynamic_array_value(source, array_type, arena=True, inline=True)
            signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, 'int64')
            literal = hir.FunctionLiteral(loc, signature, [hir.Param(source.name, 'int64')], [], None,
                'int64', hir.Block(loc, 'int64', [*prefix, hir.Return(loc, ty.BOTTOM_TYPE, value)], True))
            result.append(LoweredFunction(symbol, literal))
        return result

    def _clone_dynamic_array_value(self, node, array_type, *, arena=False, move=False, inline=False):
        # A widened length fact does not change a fixed backing allocation
        # into a descriptor. Copy from its known physical extent before
        # entering descriptor-only sharing, including at call boundaries.
        if self._array_use_representation(node) is not None:
            fixed = replace(array_type, length=self._raw_array_length(node))
            return self._clone_array_value(node, fixed, arena=arena or self._has_arena(), move=move)
        if not self._has_arena():
            return self._clone_dynamic_array_storage(node, array_type, arena=arena, move=move)
        loc = node.loc
        before, value = self._extract_array_operand(node, array_type)
        source = self._name('shared_source', loc)
        before.append(self._declare(source, value, loc))
        if not move and not inline:
            # Both the shared fast path and the fallback already return an
            # arena-owned descriptor. Outline the whole operation, including
            # the potentially large union/record element clone loop, once per
            # array type. Source evaluation remains in the caller, in order.
            result = self._name('shared_array', loc)
            before.append(self._declare(result, self._shared_array_copy_call(source, array_type, loc), loc))
            return before, result
        if move:
            before.extend(self._ensure_unique_array(source, array_type.element, loc))
            cloned, result = self._clone_dynamic_array_storage(replace(source, type=array_type), array_type, arena=arena, move=True)
            return [*before, *cloned], result
        # Always give an independently retained descriptor arena lifetime.
        # This also makes context fields independent of the caller's frame.
        cloned, result = self._clone_dynamic_array_storage(replace(source, type=array_type), array_type, arena=True)
        target = self._name('shared_array', loc)
        owner = self._name('shared_owner', loc)
        one = self._int64_literal(loc, 1)
        size = self._int64_literal(loc, 8)
        shared = [
            self._declare(owner, self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), loc),
            self._if(self._int64_comparison('__eq__', owner, one, loc), [
                self._assign(owner, self._arena_allocation(size, loc), loc),
                self._store_i64_field(owner, 0, one, loc),
                self._store_i64_field(source, ARRAY_OWNER_OFFSET, owner, loc),
                self._store_i64_field(source, ARRAY_FLAGS_OFFSET, self._int64_binary('__or__', self._load_i64_field(source, ARRAY_FLAGS_OFFSET, loc), self._int64_literal(loc, ARRAY_SHARED), loc), loc),
            ], loc),
            self._store_i64_field(owner, 0, self._int64_binary('__add__', self._load_i64_field(owner, 0, loc), one, loc), loc),
            self._assign(target, self._arena_allocation(self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc), loc),
            *[self._store_i64_field(target, offset, self._load_i64_field(source, offset, loc), loc)
              for offset in (ARRAY_DATA_OFFSET, ARRAY_LENGTH_OFFSET, ARRAY_CAPACITY_OFFSET, ARRAY_STRIDE_OFFSET, ARRAY_OWNER_OFFSET)],
            self._store_i64_field(target, ARRAY_FLAGS_OFFSET, self._int64_literal(loc, ARRAY_MUTABLE | ARRAY_ARENA_DESCRIPTOR | ARRAY_SHARED), loc),
        ]
        return [*before, self._declare(target, self._int64_literal(loc, 0), loc),
                self._if(hir.ShortCircuit(loc, 'bool', 'or', self._int64_comparison('__eq__', self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), one, loc), self._array_is_shared(source, self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), loc)),
                         shared, loc, [*cloned, self._assign(target, result, loc)])], target

    def _ensure_unique_array(self, descriptor, element, loc):
        if not self._has_arena():
            return []
        if not hasattr(self, 'unique_symbols'):
            self.unique_symbols = []
            self.pending_uniques = []
        symbol = next((name for existing, name in self.unique_symbols if existing == element), None)
        if symbol is None:
            symbol = self._internal_symbol(f'__dewy_unique_array_{len(self.unique_symbols)}')
            self.unique_symbols.append((element, symbol))
            self.pending_uniques.append((element, symbol))
        signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
        return [hir.FunctionCall(loc, ty.VOID_TYPE, hir.ExpressedIdentifier(loc, signature, symbol), [replace(descriptor, type='int64')], {})]

    def _synthesize_uniques(self):
        from .lowering_shared import LoweredFunction
        generated = []
        while getattr(self, 'pending_uniques', []):
            element, symbol = self.pending_uniques.pop(0)
            loc = self.root.loc
            source = hir.ExpressedIdentifier(loc, 'int64', '__dewy_unique_source')
            body = self._ensure_unique_array_body(source, element, loc)
            signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
            literal = hir.FunctionLiteral(loc, signature, [hir.Param(source.name, 'int64')], [], None, ty.VOID_TYPE, hir.Block(loc, ty.VOID_TYPE, body, True))
            generated.append(LoweredFunction(symbol, literal))
        return generated

    def _ensure_unique_array_body(self, descriptor, element, loc):
        source = self._name('write_array', loc)
        owner = self._name('write_owner', loc)
        one = self._int64_literal(loc, 1)
        # The outer buffer becomes independent; element copies may themselves
        # share their backing arrays. Nested places detach each ancestor.
        copied, fresh = self._clone_dynamic_array_storage(replace(source, type=ty.ArrayType(element, None)), ty.ArrayType(element, None), arena=True)
        detach = [*copied,
            self._store_i64_field(owner, 0, self._int64_binary('__sub__', self._load_i64_field(owner, 0, loc), one, loc), loc),
            *[self._store_i64_field(source, offset, self._load_i64_field(fresh, offset, loc), loc)
              for offset in (ARRAY_DATA_OFFSET, ARRAY_LENGTH_OFFSET, ARRAY_CAPACITY_OFFSET, ARRAY_STRIDE_OFFSET)],
            self._arena_release_call(fresh, self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc),
        ]
        unique = [self._arena_release_call(owner, self._int64_literal(loc, 8), loc)]
        shared = self._if(self._int64_comparison('__gt__', self._load_i64_field(owner, 0, loc), one, loc), detach, loc, unique)
        return [self._declare(source, descriptor, loc),
                self._declare(owner, self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), loc),
                self._if(self._array_is_shared(source, owner, loc), [shared, self._store_i64_field(source, ARRAY_OWNER_OFFSET, one, loc), self._store_i64_field(source, ARRAY_FLAGS_OFFSET, self._int64_binary('__and__', self._load_i64_field(source, ARRAY_FLAGS_OFFSET, loc), self._int64_literal(loc, ~ARRAY_SHARED), loc), loc)], loc)]

    def _release_owned_array(self, descriptor, loc, *, element=None, inline=False):
        if not self._has_arena():
            return self._release_unique_array(descriptor, loc, element=element)
        if not inline:
            # Owner/refcount dispatch and recursive element cleanup depend
            # only on the element representation. Keep descriptor evaluation
            # in the caller and share the complete release operation. No
            # helper-local allocation or value escapes this void call.
            symbol = next((name for existing, name in self.array_release_symbols if existing == element), None)
            if symbol is None:
                symbol = self._internal_symbol(f'__dewy_release_array_{len(self.array_release_symbols)}')
                self.array_release_symbols.append((element, symbol))
                self.pending_array_releases.append((element, symbol))
            return [self._release_value_call(symbol, descriptor, loc)]
        owner = self._name('release_owner', loc)
        one = self._int64_literal(loc, 1)
        original = self._release_unique_array(descriptor, loc, element=element)
        flags = self._load_i64_field(descriptor, ARRAY_FLAGS_OFFSET, loc)
        allocated = self._int64_comparison('__ne__', self._int64_binary('__and__', flags, self._int64_literal(loc, ARRAY_ARENA_DESCRIPTOR), loc), self._int64_literal(loc, 0), loc)
        retained = [
            self._store_i64_field(owner, 0, self._int64_binary('__sub__', self._load_i64_field(owner, 0, loc), one, loc), loc),
            self._store_i64_field(descriptor, ARRAY_OWNER_OFFSET, self._int64_literal(loc, 0), loc),
            self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, self._int64_literal(loc, 0), loc),
            self._if(allocated, [self._arena_release_call(descriptor, self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc)], loc),
        ]
        last = [self._arena_release_call(owner, self._int64_literal(loc, 8), loc),
                self._store_i64_field(descriptor, ARRAY_OWNER_OFFSET, one, loc), *original]
        release = self._if(self._array_is_shared(descriptor, owner, loc),
                           [self._if(self._int64_comparison('__gt__', self._load_i64_field(owner, 0, loc), one, loc), retained, loc, last)], loc, original)
        return [self._if(self._int64_comparison('__ne__', descriptor, self._int64_literal(loc, 0), loc), [
            self._declare(owner, self._load_i64_field(descriptor, ARRAY_OWNER_OFFSET, loc), loc),
            self._if(self._int64_comparison('__ne__', owner, self._int64_literal(loc, -1), loc), [release], loc),
        ], loc)]

    def _pin_aggregate_call(self, value, type_, loc):
        """Raw storage exposure ends COW eligibility for the exposed tree.

        Existing snapshots stay independent. Future copies of pinned arrays
        use the recursive fallback; raw pointers have no tracked lifetime, so
        pinned storage is conservatively retained for the process.
        """
        unfolded = ty.unfold(ty.strip_refinement(type_))
        if not self._is_string_valued(unfolded) and not isinstance(unfolded, (ty.ArrayType, ty.ObjectType)) and ty.runtime_union_members(type_) is None and ty.optional_payload(type_) is None:
            return []
        if not hasattr(self, 'pin_symbols'):
            self.pin_symbols = []
            self.pending_pins = []
        symbol = next((name for existing, name in self.pin_symbols if existing == type_), None)
        if symbol is None:
            symbol = self._internal_symbol(f'__dewy_pin_{len(self.pin_symbols)}')
            self.pin_symbols.append((type_, symbol))
            self.pending_pins.append((type_, symbol))
        signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
        return [hir.FunctionCall(loc, ty.VOID_TYPE, hir.ExpressedIdentifier(loc, signature, symbol), [replace(value, type='int64')], {})]

    def _synthesize_pins(self):
        from .lowering_shared import LoweredFunction
        generated = []
        while getattr(self, 'pending_pins', []):
            type_, symbol = self.pending_pins.pop(0)
            loc = self.root.loc
            source = hir.ExpressedIdentifier(loc, 'int64', '__dewy_pin_source')
            body = self._pin_aggregate_body(source, type_, loc)
            signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
            literal = hir.FunctionLiteral(loc, signature, [hir.Param(source.name, 'int64')], [], None, ty.VOID_TYPE, hir.Block(loc, ty.VOID_TYPE, body, True))
            generated.append(LoweredFunction(symbol, literal))
        return generated

    def _pin_aggregate_body(self, source, type_, loc):
        unfolded = ty.unfold(ty.strip_refinement(type_))
        if self._is_string_valued(unfolded):
            # A raw write cannot affect an earlier string snapshot. Give a
            # shared or borrowed descriptor private buffers before exposure;
            # pinned buffers then use deep copies and have process lifetime.
            owner = self._name('pinned_string_owner', loc)
            length = self._name('pinned_string_length', loc)
            copied, fresh = self._string_from_bytes(self._string_data_start(source, loc), length, loc,
                                                    frame=False, segmented_source=source)
            detach = [
                self._declare(length, self._load_i64_field(source, STRING_BYTE_LENGTH_OFFSET, loc), loc),
                *copied,
                self._if(self._int64_comparison('__gt__', owner, self._int64_literal(loc, 2), loc),
                         self._release_shared_string_buffers(source, loc), loc),
                *[self._store_i64_field(source, offset, self._load_i64_field(fresh, offset, loc), loc)
                  for offset in range(0, STRING_OWNER_OFFSET, 8)],
                self._arena_release_call(fresh, self._int64_literal(loc, STRING_DESCRIPTOR_SIZE), loc),
            ]
            return [self._declare(owner, self._load_i64_field(source, STRING_OWNER_OFFSET, loc), loc),
                    self._if(self._int64_comparison('__ge__', owner, self._int64_literal(loc, 2), loc), detach, loc),
                    self._if(self._int64_comparison('__gt__', owner, self._int64_literal(loc, 0), loc),
                             [self._store_i64_field(source, STRING_OWNER_OFFSET, self._int64_literal(loc, -1), loc)], loc)]
        if isinstance(unfolded, ty.ArrayType):
            body = self._ensure_unique_array(source, unfolded.element, loc)
            # A borrowed byte/grapheme view may keep a string descriptor in
            # owner. It is not a reference count, nor owned array storage.
            copied, fresh = self._clone_dynamic_array_storage(replace(source, type=unfolded), unfolded, arena=True)
            adopt = [*copied,
                     *[self._store_i64_field(source, offset, self._load_i64_field(fresh, offset, loc), loc)
                       for offset in (ARRAY_DATA_OFFSET, ARRAY_LENGTH_OFFSET, ARRAY_CAPACITY_OFFSET, ARRAY_STRIDE_OFFSET)],
                     self._arena_release_call(fresh, self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc)]
            body.append(self._if(self._int64_comparison('__ne__', self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), self._int64_literal(loc, 1), loc), adopt, loc))
            body.append(self._store_i64_field(source, ARRAY_OWNER_OFFSET, self._int64_literal(loc, -1), loc))
            index = self._name('pin_index', loc)
            child = self._array_load(self._array_element_address(source, index, unfolded.element, loc), unfolded.element, loc)
            pin = self._pin_aggregate_call(child, unfolded.element, loc)
            if pin:
                body.extend([self._declare(index, self._int64_literal(loc, 0), loc),
                             self._while(self._int64_comparison('__lt__', index, self._load_i64_field(source, ARRAY_LENGTH_OFFSET, loc), loc),
                                         [*pin, self._assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc), loc)], loc)])
            return [self._if(self._int64_comparison('__ne__', self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), self._int64_literal(loc, -1), loc), body, loc)]
        if isinstance(unfolded, ty.ObjectType):
            def fields(object_type, selected):
                _, offsets = self._object_layout(object_type, hir.Void(loc, ty.VOID_TYPE))
                body = []
                for field in selected:
                    pointer = self._field_address(source, offsets[field.name], loc)
                    field_type = ty.unfold(ty.strip_refinement(field.type))
                    if isinstance(field_type, ty.ArrayType) or self._is_string_valued(field_type):
                        pointer = self._load_i64_field(pointer, 0, loc)
                    body.extend(self._pin_aggregate_call(pointer, field.type, loc))
                return body
            return [*fields(unfolded, unfolded.fields), *self._by_brand(source, unfolded, loc, fields)]
        members = ty.runtime_union_members(type_)
        if members is None:
            optional = ty.optional_payload(type_)
            members = ('none', optional) if optional is not None else ()
        tag = self._optional_tag(source, loc)
        payload = self._load_i64_field(source, 8, loc)
        arms = []
        for member in members:
            body = self._pin_aggregate_call(payload, member, loc)
            if body:
                arms.append(hir.IfArm(loc, ty.VOID_TYPE, self._tag_is(tag, member, loc), hir.Block(loc, ty.VOID_TYPE, body, True)))
        return [hir.Flow(loc, ty.VOID_TYPE, arms, None)] if arms else []
