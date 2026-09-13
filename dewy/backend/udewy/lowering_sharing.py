"""Provisional copy-on-write backing storage; source values stay independent.

Descriptors remain private. Owner 0 denotes frame/static data, 1 uniquely
owned arena data, and an aligned pointer >1 a shared reference-count word.
Only arena data can be shared. Mutation detaches before exposing an element
place; final release visits the elements exactly once. See bootstrap/PERFORMANCE.md
for the open long-term predictability/zero-cost design question.
"""
from dataclasses import replace

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
    ARRAY_STRIDE_OFFSET,
)


class _ArraySharing:
    def _extract_write_route(self, node):
        """Evaluate a nested place once, detaching enclosing array buffers."""
        if isinstance(node, hir.Index) and self._array_use_representation(node.array) is None:
            prelude, array = self._extract_write_route(node.array)
            index = node.constant_index
            if index is None:
                before, index = self._extract_expression(node.index)
                prelude.extend(before)
            prelude.extend(self._ensure_unique_array(array, node.type, node.loc))
            address = self._array_element_address(array, index, node.type, node.loc)
            return prelude, self._array_load(address, node.type, node.loc)
        if isinstance(node, hir.MemberAccess):
            prelude, value = self._extract_write_route(node.value)
            base = self._name('write_object', node.loc)
            prelude.append(self._declare(base, replace(value, type='int64'), node.loc))
            before, result = self._extract_member_access(replace(node, value=replace(base, type=node.value.type)))
            return [*prelude, *before], result
        return self._extract_expression(node)

    def _note_array_copy(self, size, loc):
        helper = next((candidate for candidate in self.functions if candidate.logical_name.endswith('_arena_note_copy')), None)
        if helper is None:
            return []
        signature = ty.FunctionType([ty.PosOrKwArg(None, 'int64')], [], None, ty.VOID_TYPE)
        return [hir.FunctionCall(loc, ty.VOID_TYPE, hir.ExpressedIdentifier(loc, signature, helper.symbol), [size], {})]

    def _clone_dynamic_array_value(self, node, array_type, *, arena=False, move=False):
        if not self._has_arena():
            return self._clone_dynamic_array_storage(node, array_type, arena=arena, move=move)
        loc = node.loc
        before, value = self._extract_expression(node)
        source = self._name('shared_source', loc)
        before.append(self._declare(source, value, loc))
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
            ], loc),
            self._store_i64_field(owner, 0, self._int64_binary('__add__', self._load_i64_field(owner, 0, loc), one, loc), loc),
            self._assign(target, self._arena_allocation(self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc), loc),
            *[self._store_i64_field(target, offset, self._load_i64_field(source, offset, loc), loc)
              for offset in (ARRAY_DATA_OFFSET, ARRAY_LENGTH_OFFSET, ARRAY_CAPACITY_OFFSET, ARRAY_STRIDE_OFFSET, ARRAY_OWNER_OFFSET)],
            self._store_i64_field(target, ARRAY_FLAGS_OFFSET, self._int64_literal(loc, ARRAY_MUTABLE | ARRAY_ARENA_DESCRIPTOR), loc),
        ]
        return [*before, self._declare(target, self._int64_literal(loc, 0), loc),
                self._if(self._int64_comparison('__gt__', self._load_i64_field(source, ARRAY_OWNER_OFFSET, loc), self._int64_literal(loc, 0), loc),
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
                self._if(self._int64_comparison('__gt__', owner, one, loc), [shared, self._store_i64_field(source, ARRAY_OWNER_OFFSET, one, loc)], loc)]

    def _release_owned_array(self, descriptor, loc, *, element=None):
        if not self._has_arena():
            return self._release_unique_array(descriptor, loc, element=element)
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
        release = self._if(self._int64_comparison('__gt__', owner, one, loc),
                           [self._if(self._int64_comparison('__gt__', self._load_i64_field(owner, 0, loc), one, loc), retained, loc, last)], loc, original)
        return [self._declare(owner, self._load_i64_field(descriptor, ARRAY_OWNER_OFFSET, loc), loc),
                self._if(self._int64_comparison('__ne__', owner, self._int64_literal(loc, -1), loc), [release], loc)]

    def _pin_aggregate_call(self, value, type_, loc):
        """Raw storage exposure ends COW eligibility for the exposed tree.

        Existing snapshots stay independent. Future copies of pinned arrays
        use the recursive fallback; raw pointers have no tracked lifetime, so
        pinned storage is conservatively retained for the process.
        """
        unfolded = ty.unfold(ty.strip_refinement(type_))
        if not isinstance(unfolded, (ty.ArrayType, ty.ObjectType)) and ty.runtime_union_members(type_) is None and ty.optional_payload(type_) is None:
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
        if isinstance(unfolded, ty.ArrayType):
            body = self._ensure_unique_array(source, unfolded.element, loc)
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
                    if isinstance(field_type, ty.ArrayType):
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
