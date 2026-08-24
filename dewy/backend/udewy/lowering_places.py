"""Place (`@`) argument lowering: projected storage selection and writebacks.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from dataclasses import replace

from ...semantic import hir, ty
from ...semantic.hir_display import type_to_dewy


class _PlaceLowering:
    def _place_runtime_type(self, type_: ty.Type, node: hir.AST) -> ty.Type:
        """Return the directly loadable representation held by a place cell."""

        runtime_type = self._lower_runtime_value_type(type_)
        if not isinstance(runtime_type, (str, ty.FunctionType)):
            self._target_error(
                node,
                f'place storage for `{type_to_dewy(type_)}`',
            )
        if isinstance(runtime_type, ty.FunctionType):
            self._target_error(node, 'function-handle place storage')
        return runtime_type

    def _place_storage_bytes(self, type_: ty.Type, node: hir.AST) -> int:
        """Size of one non-escaping cell containing a lowered place value."""

        if type_ == 'bool':
            return 1
        layout = ty.fixed_integer_layout(type_)
        if layout is not None:
            width, _signed = layout
            return max(1, width // 8)
        if self._is_handle_type(type_):
            return 8
        self._target_error(
            node,
            f'place storage for `{type_to_dewy(type_)}`',
        )

    def _new_place_name(self, role: str) -> str:
        while True:
            name = f'__dewy_place_{role}_{self.next_place_temp}'
            self.next_place_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    def _materialize_place_argument(
        self,
        node: hir.Place,
    ) -> tuple[list[hir.AST], hir.AST, list[hir.AST]]:
        """Create one non-escaping pointer cell and a post-call writeback."""

        target = node.target
        if isinstance(target, (hir.MemberAccess, hir.Index)):
            prelude, storage = self._extract_projected_place_storage(target)
            return prelude, replace(storage, type='int64'), []
        if isinstance(node.type, ty.ObjectType):
            prelude, storage = self._extract_object_pointer(target)
            return prelude, replace(storage, type='int64'), []
        if ty.optional_payload(node.type) is not None:
            return [], replace(target, type='int64'), []
        if (
            isinstance(node.type, ty.ArrayType)
            and self._array_use_representation(target) is not None
        ):
            raise TypeError(
                'INTERNAL ERROR: place argument retained a descriptor-free array'
            )
        runtime_type = self._place_runtime_type(node.type, node)
        cell_name = self._new_place_name(f'cell_{target.name}')
        cell = hir.ExpressedIdentifier(node.loc, 'int64', cell_name)
        loaded = self._value_load(cell, runtime_type, node.loc)
        writeback_target = replace(target, type=runtime_type)
        postlude: list[hir.AST] = [hir.Assign(
            node.loc,
            ty.VOID_TYPE,
            writeback_target,
            '=',
            loaded,
        )]
        outer_cell = (
            self.current_place_parameter_cells.get(target.binding_id)
            if target.binding_id is not None
            else None
        )
        if outer_cell is not None:
            postlude.extend(
                self._value_store(
                    writeback_target,
                    outer_cell,
                    runtime_type,
                    node.loc,
                )
            )
        prelude: list[hir.AST] = [
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                cell_name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(
                        node.loc,
                        self._place_storage_bytes(runtime_type, node),
                    )],
                    'int64',
                    node.loc,
                ),
            ),
            *self._value_store(
                writeback_target,
                cell,
                runtime_type,
                node.loc,
            ),
        ]
        return prelude, cell, postlude

    def _extract_projected_place_storage(
        self,
        target: hir.MemberAccess | hir.Index,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Evaluate a place route once and return its final storage address."""

        if isinstance(target, hir.MemberAccess):
            prelude, obj = self._extract_object_pointer(target.value)
            if not isinstance(target.value.type, ty.ObjectType):
                self._target_error(target, 'projected member place requires an object')
            _size, offsets = self._object_layout(target.value.type, target)
            return prelude, self._field_address(
                obj,
                offsets[target.name],
                target.loc,
            )

        raw_representation = self._array_use_representation(target.array)
        prelude, array = self._extract_expression(target.array)
        index: int | hir.AST = target.constant_index
        if index is None:
            index_prelude, index = self._extract_expression(target.index)
            prelude.extend(index_prelude)
        address = (
            self._pointer_element_address(
                array,
                index,
                self._array_element_layout(target.type, target)[0],
                target.loc,
            )
            if raw_representation is not None
            else self._array_element_address(
                array,
                index,
                target.type,
                target.loc,
            )
        )
        if target.type == 'uint8' and raw_representation is None:
            cow = self._ensure_mutable_byte_array(array, target.loc)
            if cow:
                prelude.extend(cow)
                address = self._array_element_address(
                    array,
                    index,
                    target.type,
                    target.loc,
                )
        if isinstance(target.type, ty.ObjectType):
            return prelude, self._array_load(address, target.type, target.loc)
        return prelude, address

    def _finish_scalar_call_place_writebacks(
        self,
        call: hir.FunctionCall,
        prelude: list[hir.AST],
        postlude: list[hir.AST],
    ) -> tuple[list[hir.AST], hir.AST]:
        """Keep a scalar call result live while place cells are written back."""

        if not postlude:
            return prelude, call
        if call.type == ty.VOID_TYPE:
            return [*prelude, call, *postlude], hir.Void(call.loc, ty.VOID_TYPE)
        runtime_type = self._lower_runtime_value_type(call.type)
        target = replace(self._new_flow_temp(call), type=runtime_type)
        return [
            *prelude,
            hir.Declare(
                call.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                runtime_type,
                replace(call, type=runtime_type),
            ),
            *postlude,
        ], target

