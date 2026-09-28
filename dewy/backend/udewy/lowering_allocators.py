"""Conservative scoped allocator placement, separate from source copy policy.

The storage helpers preserve owner allocation even across a nested context.
Placement still requires proving that ordinary calls and stores cannot publish
region values into longer-lived storage. Unknown routes retain heap placement.
"""
from collections import defaultdict, deque

from ...utils import dataclass_replace as replace
from ...semantic import hir, ty
from . import borrowing
from .lowering_shared import PlacementNote


def _body_nodes(root):
    pending, seen = [root], set()
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield node
        if not isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
            pending.extend(hir.children(node))


class _AllocatorLowering:
    def _cell_for_store_owner(self, value, type_, anchor, loc):
        """Promote an owned tag cell after RHS evaluation, before publishing it."""
        if not self._has_arena() or self._runtime_helper('_allocator_enter_for') is None:
            return [], value
        if not (self._is_optional_element(type_) or self._is_union_element(type_)):
            return [], value
        result = self._name('store_cell', loc)
        previous = self._name('store_allocator', loc)
        slot = self._name('promoted_cell_slot', loc)
        promoted = [self._declare(slot, self._intrinsic_call('__alloca__', [self._int64_literal(loc, 8)], 'int64', loc), loc)]
        if self._is_optional_element(type_):
            promoted.extend(self._copy_optional_element(result, slot, type_, loc))
        else:
            promoted.extend(self._copy_union_element(result, slot, type_, loc))
        members = self._field_union_members(ty.strip_refinement(type_))
        assert members is not None
        promoted.extend(self._release_cell_payload(result, members, loc))
        promoted.extend([
            self._arena_release_call(result, self._int64_literal(loc, 16), loc),
            hir.Assign(loc, ty.VOID_TYPE, result, '=', self._intrinsic_call('__load_i64__', [slot], 'int64', loc)),
        ])
        return [
            self._declare(result, value, loc),
            self._declare(previous, self._region_call('_allocator_enter_for', [anchor], loc, 'int64'), loc),
            self._if(self._intrinsic_call('__not__', [self._shareable_storage(result, loc)], 'bool', loc), promoted, loc),
            self._region_call('_allocator_exit', [previous], loc, ty.VOID_TYPE),
        ], result

    @staticmethod
    def _allocator_owned(type_):
        plain = ty.structural_base(type_)
        return (isinstance(plain, (ty.ArrayType, ty.ObjectType)) or ty.string_valued(plain)
                or ty.runtime_union_members(plain) is not None or ty.optional_payload(plain) is not None)

    def _allocator_stores_owned(self, node):
        if isinstance(node, (hir.Assign, hir.MemberAssign, hir.IndexAssign)):
            return self._allocator_owned(node.value.type)
        if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod):
            return any(self._allocator_owned(arg.type) for arg in [*node.pos_args, *node.kw_args.values()])
        return True

    def _allocator_unknown_call(self, node):
        callee = node.func
        if isinstance(callee, hir.ExpressedIdentifier):
            # Unbound source operators and machine intrinsics do not invoke
            # arbitrary Dewy code. A bound name must resolve through checking.
            return callee.binding_id is not None or not (
                callee.name.startswith('__') and callee.name.endswith('__'))
        if isinstance(callee, hir.ArrayMethod):
            return callee.name == 'sort' and 'key' in node.kw_args
        return not isinstance(callee, (hir.DictMethod, hir.FunctionLiteral))

    def _allocator_call_hazards(self):
        if self.allocator_hazards is not None:
            return self.allocator_hazards
        analysis = self.allocator_analysis
        hazards, callers = set(), defaultdict(set)
        for literal in analysis.literals:
            key = id(literal)
            params = borrowing.literal_params(literal)
            nodes = [node for root in [literal.body, *(p.value for p in params if isinstance(p, hir.BoundParam))]
                     for node in _body_nodes(root)]
            local = {p.binding_id for p in params}
            local.update(node.binding_id for node in nodes if isinstance(node, hir.Declare))
            local.update(node.target.binding_id for node in nodes if isinstance(node, hir.IteratorExpression))
            for node in nodes:
                if self._allocator_stores_owned(node) and any(
                        borrowing.root_binding(target) not in local for target in borrowing.write_targets(node)):
                    hazards.add(key)
                if isinstance(node, hir.FunctionCall):
                    targets = analysis._direct_targets(node)
                    if targets is not None:
                        for target in targets:
                            callers[id(target)].add(key)
                    elif self._allocator_unknown_call(node):
                        hazards.add(key)
        pending = deque(hazards)
        while pending:
            for caller in callers[pending.popleft()]:
                if caller not in hazards:
                    hazards.add(caller)
                    pending.append(caller)
        self.allocator_hazards = hazards
        return hazards

    def _allocator_fallback(self, block):
        for name in ('_allocator_enter', '_allocator_exit', '_shareable', '_arena_alloc_for', '_allocator_enter_for'):
            if self._runtime_helper(name) is None:
                return f'missing allocator runtime helper `{name}`'
        # Scalar exits unwind through the ordinary lexical cleanup pass.
        # Aggregate results still need a separate copy-out after restoration.
        if self._allocator_owned(block.type):
            return 'hosted aggregate copy-out still uses the enclosing allocator'
        nodes = [node for item in block.items for node in _body_nodes(item)]
        if any(isinstance(node, hir.Return) and node.item is not None
               and self._allocator_owned(node.item.type) for node in nodes):
            return 'hosted aggregate return copy-out still uses the enclosing allocator'
        declared = {node.binding_id for node in nodes if isinstance(node, hir.Declare)}
        declared.update(node.target.binding_id for node in nodes if isinstance(node, hir.IteratorExpression))
        arenas = {id(node.arena) for node in nodes if isinstance(node, hir.AllocatorBlock)}
        hazards = self._allocator_call_hazards()
        for node in nodes:
            if isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
                return 'contains a function whose captured storage may outlive the block'
            if isinstance(node, hir.IteratorExpression) or id(node) in arenas:
                continue
            if self._allocator_stores_owned(node) and any(
                    borrowing.root_binding(target) not in declared for target in borrowing.write_targets(node)):
                return 'may store owned storage outside the block'
            if isinstance(node, hir.DictMethod) and borrowing.root_binding(node.dictionary) not in declared:
                return 'may update a dictionary outside the block'
            if isinstance(node, hir.FunctionCall):
                targets = self.allocator_analysis._direct_targets(node)
                if targets is None:
                    if self._allocator_unknown_call(node):
                        return 'calls unknown code whose storage lifetime is not established'
                else:
                    for target in targets:
                        function = self.function_by_literal.get(id(target))
                        if id(target) in hazards:
                            return 'calls code that may publish storage or call unknown code'
                        if function is not None and self.lifted.get(id(function)):
                            return 'calls code with captured storage'
        return None

    def _transform_allocator(self, node):
        reason = self._allocator_fallback(node)
        items = [value for item in node.items if (value := self._transform_node(item)) is not None]
        if reason is not None:
            self.placement_notes.append(PlacementNote(self.srcfile, node.loc, reason))
            return replace(node, items=items)
        previous = hir.ExpressedIdentifier(node.loc, 'int64', self._new_result_name())
        arena = self._require_node(self._transform_node(node.arena))
        entry = self._region_call('_allocator_enter', [arena], node.loc, 'int64')
        exit_ = self._region_call('_allocator_exit', [previous], node.loc, ty.VOID_TYPE)
        self.allocator_restorations[previous.name] = exit_
        return replace(node, arena=arena, items=[
            hir.Declare(node.loc, ty.VOID_TYPE, 'let', previous.name, 'int64', entry),
            *items,
        ])
