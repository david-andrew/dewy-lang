"""Array lowering: representation analysis, call-boundary borrowing, storage, copies, results, and array iteration.

Split from ``lower.py``; methods run as part of ``_Lowerer``.
"""

from __future__ import annotations

from collections import defaultdict
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
    ArrayCallBoundaryAnalysis,
    ArrayParameterAnalysis,
    ArrayRepresentation,
    ArrayUse,
    _Binding,
    _FunctionDef,
    _Scope,
)


class _ArrayLowering:
    def _array_representation(
        self,
        declaration: hir.Declare,
    ) -> ArrayRepresentation:
        if declaration.binding_id is None:
            return 'descriptor'
        return self.array_representations.get(
            declaration.binding_id,
            'descriptor',
        )

    def _static_array_global(
        self,
        declaration: hir.Declare,
        representation: Literal['static_words', 'static_bytes'],
    ) -> hir.Declare:
        if representation == 'static_words':
            if not isinstance(declaration.expr, hir.ArrayLiteral):
                raise TypeError(
                    'INTERNAL ERROR: static-word representation requires an array literal'
                )
            initializer = self._intrinsic_call(
                '__static_words__',
                [
                    self._static_word_initializer_argument(
                        item,
                        declaration.expr.type.element,
                        set(),
                    )
                    for item in declaration.expr.items
                ],
                'int64',
                declaration.loc,
            )
        else:
            if not isinstance(declaration.expr, hir.RepresentationCast):
                raise TypeError(
                    'INTERNAL ERROR: static-byte representation requires based data'
                )
            initializer = declaration.expr.expr
        return replace(
            declaration,
            annotation='int64',
            expr=initializer,
        )

    def _static_word_initializer_argument(
        self,
        node: hir.AST,
        element_type: ty.Type,
        seen: set[int],
    ) -> hir.AST:
        while isinstance(node, (hir.ValueCast, hir.Transmute)):
            node = node.expr
        if isinstance(element_type, ty.FunctionType):
            return node
        if isinstance(node, hir.Integer):
            return node
        if not isinstance(node, hir.ExpressedIdentifier) or node.binding_id is None:
            raise TypeError('INTERNAL ERROR: unstable static-word initializer')
        if node.binding_id in seen:
            raise TypeError('INTERNAL ERROR: cyclic static-word initializer')
        declaration = self._declaration_for_binding(node.binding_id)
        if declaration is None:
            raise TypeError('INTERNAL ERROR: missing static-word alias declaration')
        return self._static_word_initializer_argument(
            declaration.expr,
            element_type,
            {*seen, node.binding_id},
        )

    def _record_local_array_alias(
        self,
        declaration: hir.Declare,
        binding: _Binding,
        scope: _Scope,
        current_function: _FunctionDef | None,
    ) -> bool:
        """Record copy provenance for representation analysis.

        The edge does not represent a Dewy-level alias: lowering must still
        give the new binding independent mutable contents.
        """

        if (
            current_function is None
            or binding.semantic_id is None
            or not isinstance(declaration.annotation or declaration.expr.type, ty.ArrayType)
        ):
            return False
        source_node = declaration.expr
        while (
            isinstance(source_node, hir.Block)
            and not source_node.scoped
            and len(source_node.items) == 1
        ):
            source_node = source_node.items[0]
        if not isinstance(source_node, hir.ExpressedIdentifier):
            return False
        source = (
            self.binding_by_semantic_id.get(source_node.binding_id)
            if source_node.binding_id is not None
            else scope.resolve(source_node.name)
        )
        if (
            source is None
            or source.semantic_id is None
            or source.kind not in {'param', 'value'}
            or source.owner_function is not current_function
            or binding.owner_function is not current_function
            or not isinstance(source_node.type, ty.ArrayType)
        ):
            return False
        self.array_alias_edges[binding.semantic_id] = source.semantic_id
        return True

    def _analyze_array_aliases_and_parameters(self) -> None:
        self._build_array_alias_groups()
        self._build_array_parameter_analyses()
        boundary_uses = self._analyze_array_call_boundaries()
        for uses in self.array_uses.values():
            uses.discard('call_boundary_pending')
        for binding_id, uses in boundary_uses.items():
            self.array_uses[binding_id].update(uses)
        self._refresh_array_group_uses()
        self._build_array_parameter_analyses()

    def _build_array_alias_groups(self) -> None:
        # These groups collect copy provenance so representation requirements
        # propagate between related bindings. They are not observable aliases.
        binding_ids = {
            *self.array_declarations,
            *self.array_parameters,
            *self.array_alias_edges,
            *self.array_alias_edges.values(),
        }
        parents = {binding_id: binding_id for binding_id in binding_ids}

        def root(binding_id: int) -> int:
            while parents[binding_id] != binding_id:
                parents[binding_id] = parents[parents[binding_id]]
                binding_id = parents[binding_id]
            return binding_id

        for alias_id, source_id in self.array_alias_edges.items():
            alias_root = root(alias_id)
            source_root = root(source_id)
            if alias_root != source_root:
                parents[alias_root] = source_root

        members_by_root: dict[int, set[int]] = defaultdict(set)
        for binding_id in binding_ids:
            members_by_root[root(binding_id)].add(binding_id)

        self.array_alias_groups = {}
        self.array_alias_group_by_binding = {}
        for members in members_by_root.values():
            group_id = min(members)
            group = frozenset(members)
            self.array_alias_groups[group_id] = group
            for binding_id in group:
                self.array_alias_group_by_binding[binding_id] = group_id
        self._refresh_array_group_uses()

    def _refresh_array_group_uses(self) -> None:
        self.array_group_uses = {
            group_id: frozenset(
                use
                for binding_id in group
                for use in self.array_uses.get(binding_id, set())
            )
            for group_id, group in self.array_alias_groups.items()
        }

    def _build_array_parameter_analyses(self) -> None:
        self.array_parameter_analyses = {}
        # A read-only parameter may borrow the caller's storage because the
        # sharing is unobservable. A writing parameter receives a value copy.
        allowed_uses: set[ArrayUse] = {
            'length',
            'index_read',
            'safe_call_boundary',
            'copy_call_boundary',
        }
        for binding_id, (function, parameter) in self.array_parameters.items():
            group_id = self.array_alias_group_by_binding[binding_id]
            group = self.array_alias_groups[group_id]
            uses: frozenset[ArrayUse] = frozenset(
                use
                for use in self.array_uses.get(binding_id, set())
                if use != 'alias'
            )
            # The semantic effect summary proves whether the function body can
            # write to or retain the parameter, including transitively through
            # place-forwarded calls and through object-element handles, so it
            # alone decides borrow safety. The local use-set check remains as
            # a fallback for parameters without a semantic summary; it cannot
            # see handle-hidden mutation, so it keeps the object-element ban.
            summary = self.program_effects.for_param_binding(binding_id)
            adapter_safe = (
                summary.read_only
                if summary is not None
                else (
                    uses <= allowed_uses
                    and not self._array_type_contains_object(parameter.type)
                )
            )
            self.array_parameter_analyses[binding_id] = ArrayParameterAnalysis(
                function,
                parameter,
                group,
                uses,
                adapter_safe,
            )

    @classmethod
    def _array_type_contains_object(cls, array_type: ty.ArrayType) -> bool:
        """Whether element mutation can be hidden behind an object handle."""

        element = array_type.element
        return isinstance(element, ty.ObjectType) or (
            isinstance(element, ty.ArrayType)
            and cls._array_type_contains_object(element)
        )

    @staticmethod
    def _call_place_argument_roots(call: hir.FunctionCall) -> set[int]:
        """Semantic binding ids whose storage a call's place arguments expose."""
        roots: set[int] = set()
        for argument in [*call.pos_args, *call.kw_args.values()]:
            if not isinstance(argument, hir.Place):
                continue
            target: hir.AST = argument.target
            while isinstance(target, (hir.MemberAccess, hir.Index)):
                target = (
                    target.value
                    if isinstance(target, hir.MemberAccess)
                    else target.array
                )
            if (
                isinstance(target, hir.ExpressedIdentifier)
                and target.binding_id is not None
            ):
                roots.add(target.binding_id)
        return roots

    def _analyze_array_call_boundaries(self) -> dict[int, set[ArrayUse]]:
        boundary_uses: dict[int, set[ArrayUse]] = defaultdict(set)
        self.array_call_boundary_analyses = {}
        for call in self.array_calls:
            function = self._direct_call_function(call)
            place_roots = self._call_place_argument_roots(call)
            for position, argument, parameter in self._call_array_arguments(
                call,
                function,
            ):
                source = self._array_argument_binding(argument)
                source_id = (
                    source.semantic_id
                    if source is not None and source.semantic_id is not None
                    else None
                )
                group = (
                    self.array_alias_groups[
                        self.array_alias_group_by_binding[source_id]
                    ]
                    if source_id in self.array_alias_group_by_binding
                    else frozenset()
                )
                parameter_analysis = (
                    self.array_parameter_analyses.get(parameter.binding_id)
                    if parameter is not None and parameter.binding_id is not None
                    else None
                )
                raw_kind = self._potential_raw_array_group(group)
                safe = (
                    function is not None
                    and parameter_analysis is not None
                    and parameter_analysis.adapter_safe
                    and source is not None
                    # A place argument in the same call exposing the same
                    # binding could write mid-call; a borrowed value argument
                    # would observe those writes, so the boundary must copy.
                    and source_id not in place_roots
                    and (
                        raw_kind is None
                        or self._raw_array_group_uses_are_safe(group, raw_kind)
                    )
                )
                if source_id is not None:
                    boundary_uses[source_id].add(
                        'safe_call_boundary' if safe else 'copy_call_boundary'
                    )
                self.array_call_boundary_analyses[(id(call), position)] = (
                    ArrayCallBoundaryAnalysis(
                        function,
                        argument,
                        position,
                        parameter,
                        source_id,
                        group,
                        safe,
                    )
                )
        return boundary_uses

    @staticmethod
    def _call_array_arguments(
        call: hir.FunctionCall,
        function: _FunctionDef | None,
    ) -> list[tuple[int | str, hir.AST, hir.Param | None]]:
        positional_parameters = (
            function.literal.pos_or_kw_args if function is not None else []
        )
        named_parameters = (
            {
                parameter.name: parameter
                for parameter in [
                    *function.literal.pos_or_kw_args,
                    *function.literal.kw_only_args,
                ]
            }
            if function is not None
            else {}
        )
        arguments: list[tuple[int | str, hir.AST, hir.Param | None]] = []
        for index, argument in enumerate(call.pos_args):
            if isinstance(argument, hir.Place):
                continue
            if isinstance(argument.type, ty.ArrayType):
                parameter = (
                    positional_parameters[index]
                    if index < len(positional_parameters)
                    else None
                )
                arguments.append((index, argument, parameter))
        for name, argument in call.kw_args.items():
            if isinstance(argument, hir.Place):
                continue
            if isinstance(argument.type, ty.ArrayType):
                arguments.append((name, argument, named_parameters.get(name)))
        return arguments

    def _array_argument_binding(self, node: hir.AST) -> _Binding | None:
        while isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        if not isinstance(node, hir.ExpressedIdentifier):
            return None
        return self.identifier_bindings.get(id(node))

    def _potential_raw_array_group(
        self,
        group: frozenset[int],
    ) -> Literal['stack_data', 'static_words', 'static_bytes'] | None:
        local_literals = [
            declaration
            for binding_id in group
            if (
                (declaration := self.array_declarations.get(binding_id)) is not None
                and self.binding_by_semantic_id[binding_id].owner_function is not None
                and isinstance(declaration.expr, hir.ArrayLiteral)
                and isinstance(declaration.expr.type, ty.ArrayType)
                and declaration.expr.type.length == len(declaration.expr.items)
            )
        ]
        if len(local_literals) == 1:
            return 'stack_data'
        if len(group) != 1:
            return None
        binding_id = next(iter(group))
        declaration = self.array_declarations.get(binding_id)
        binding = self.binding_by_semantic_id.get(binding_id)
        if (
            declaration is None
            or binding is None
            or binding.owner_function is not None
            or declaration.decltype != 'const'
        ):
            return None
        array_type = declaration.annotation or declaration.expr.type
        if not isinstance(array_type, ty.ArrayType):
            return None
        if (
            isinstance(declaration.expr, hir.ArrayLiteral)
            and declaration.expr.items
            and self._static_word_array_is_stable(
                declaration.expr,
                array_type,
            )
        ):
            return 'static_words'
        if (
            array_type.element == 'uint8'
            and self._static_binary_array_initializer(declaration.expr, set())
            is not None
        ):
            return 'static_bytes'
        return None

    def _raw_array_group_uses_are_safe(
        self,
        group: frozenset[int],
        raw_kind: Literal['stack_data', 'static_words', 'static_bytes'],
    ) -> bool:
        uses = {
            use
            for binding_id in group
            for use in self.array_uses.get(binding_id, set())
        } - {'alias', 'call_boundary_pending'}
        allowed: set[ArrayUse] = {'length', 'index_read'}
        allowed.add('copy_call_boundary')
        if raw_kind == 'stack_data':
            allowed.add('index_write')
        return uses <= allowed

    def _classify_array_representations(self) -> None:
        self._analyze_array_aliases_and_parameters()
        allowed_uses: set[ArrayUse] = {
            'length',
            'index_read',
            'index_write',
            'safe_call_boundary',
            'copy_call_boundary',
        }
        for group_id, group in self.array_alias_groups.items():
            roots = [
                binding_id
                for binding_id in group
                if (
                    (node := self.array_declarations.get(binding_id)) is not None
                    and self.binding_by_semantic_id[binding_id].owner_function
                    is not None
                    and isinstance(node.expr, hir.ArrayLiteral)
                    and isinstance(node.expr.type, ty.ArrayType)
                    and node.expr.type.length == len(node.expr.items)
                )
            ]
            group_uses: frozenset[ArrayUse] = frozenset(
                use for use in self.array_group_uses[group_id] if use != 'alias'
            )
            if len(roots) == 1 and group_uses <= allowed_uses:
                for binding_id in group:
                    if binding_id in self.array_declarations:
                        self.array_representations[binding_id] = 'stack_data'

        for binding_id, node in self.array_declarations.items():
            binding = self.binding_by_semantic_id[binding_id]
            if (
                binding.owner_function is not None
                or node.decltype != 'const'
                or not isinstance(node.annotation or node.expr.type, ty.ArrayType)
            ):
                continue
            uses = self.array_uses.get(binding_id, set())
            if not uses <= {
                'length',
                'index_read',
                'safe_call_boundary',
                'copy_call_boundary',
            }:
                continue
            array_type = node.annotation or node.expr.type
            assert isinstance(array_type, ty.ArrayType)
            if (
                isinstance(node.expr, hir.ArrayLiteral)
                and node.expr.items
                and self._static_word_array_is_stable(
                    node.expr,
                    array_type,
                )
            ):
                self.array_representations[binding_id] = 'static_words'
            elif (
                array_type.element == 'uint8'
                and self._static_binary_array_initializer(node.expr, set())
                is not None
            ):
                self.array_representations[binding_id] = 'static_bytes'

    def _static_word_array_is_stable(
        self,
        node: hir.ArrayLiteral,
        array_type: ty.ArrayType,
    ) -> bool:
        element = array_type.element
        if not (
            isinstance(element, str)
            and element in {'int64', 'uint64'}
            or isinstance(element, ty.FunctionType)
        ):
            return False
        return all(
            self._static_word_is_stable(item, element, set())
            for item in node.items
        )

    def _static_word_is_stable(
        self,
        node: hir.AST,
        element_type: ty.Type,
        seen: set[int],
    ) -> bool:
        while isinstance(node, (hir.ValueCast, hir.Transmute)):
            node = node.expr
        if isinstance(element_type, ty.FunctionType):
            if not isinstance(node, hir.ExpressedIdentifier):
                return False
            binding = self.identifier_bindings.get(id(node))
            return (
                binding is not None
                and binding.kind == 'function'
                and isinstance(node.type, ty.FunctionType)
                and ty.TypeSystem().is_subtype(node.type, element_type)
            )
        if isinstance(node, hir.Integer):
            return (
                isinstance(node.type, ty.IntegerLiteralType)
                and ty.integer_literal_fits(node.value, element_type)
                or node.type == element_type
            )
        if not isinstance(node, hir.ExpressedIdentifier):
            return False
        binding = self.identifier_bindings.get(id(node))
        if (
            binding is None
            or binding.semantic_id is None
            or binding.semantic_id in seen
            or binding.owner_function is not None
            or binding.expr is None
        ):
            return False
        declaration = self._declaration_for_binding(binding.semantic_id)
        return (
            declaration is not None
            and declaration.decltype == 'const'
            and self._static_word_is_stable(
                binding.expr,
                element_type,
                {*seen, binding.semantic_id},
            )
        )

    def _static_binary_array_initializer(
        self,
        node: hir.AST,
        seen: set[int],
    ) -> hir.AST | None:
        if not isinstance(node, hir.RepresentationCast):
            return None
        source = node.expr
        if isinstance(source, hir.BasedString):
            return source
        if not isinstance(source, hir.ExpressedIdentifier):
            return None
        binding = self.identifier_bindings.get(id(source))
        if (
            binding is None
            or binding.semantic_id is None
            or binding.semantic_id in seen
            or binding.owner_function is not None
            or binding.expr is None
        ):
            return None
        declaration = self._declaration_for_binding(binding.semantic_id)
        if declaration is None or declaration.decltype != 'const':
            return None
        if isinstance(binding.expr, hir.BasedString):
            return source
        nested = self._static_binary_array_initializer(
            binding.expr,
            {*seen, binding.semantic_id},
        )
        return source if nested is not None else None

    @staticmethod
    def _static_binary_array_source(node: hir.AST) -> hir.AST | None:
        if not isinstance(node, hir.RepresentationCast):
            return None
        if not isinstance(node.type, ty.ArrayType) or node.type.element != 'uint8':
            return None
        if not isinstance(node.expr.type, ty.BinaryLiteralType):
            return None
        if isinstance(node.expr, (hir.BasedString, hir.ExpressedIdentifier)):
            return node.expr
        return None

    def _array_use_representation(
        self,
        node: hir.AST,
    ) -> Literal['stack_data', 'static_words', 'static_bytes'] | None:
        while isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            node = node.items[0]
        if not isinstance(node, hir.ExpressedIdentifier):
            return None
        if node.binding_id is None:
            return None
        representation = self.array_representations.get(node.binding_id)
        if representation == 'stack_data':
            return 'stack_data'
        if representation == 'static_words':
            return 'static_words'
        if representation == 'static_bytes':
            return 'static_bytes'
        return None

    def _materialize_array_call_argument(
        self,
        node: hir.AST,
        boundary: ArrayCallBoundaryAnalysis,
    ) -> tuple[list[hir.AST], hir.AST]:
        if boundary.source_binding_id is None:
            return self._extract_expression(node)
        representation = self.array_representations.get(
            boundary.source_binding_id,
            'descriptor',
        )
        if representation == 'descriptor':
            return self._extract_expression(node)
        source_type = next(
            declaration.expr.type
            for binding_id in boundary.source_alias_group
            if (
                (declaration := self.array_declarations.get(binding_id)) is not None
                and isinstance(declaration.expr.type, ty.ArrayType)
                and declaration.expr.type.length is not None
            )
        )
        assert isinstance(source_type, ty.ArrayType)
        assert source_type.length is not None
        element_bytes, _signed = self._array_element_layout(
            source_type.element,
            node,
        )
        source_prelude, data = self._extract_expression(node)
        descriptor = self._new_array_temp(
            hir.ArrayLiteral(node.loc, source_type, [])
        )
        descriptor_word = replace(descriptor, type='int64')
        flags = (
            ARRAY_BORROWED_STATIC
            if representation == 'static_bytes'
            else ARRAY_MUTABLE
        )
        statements: list[hir.AST] = [
            *source_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                descriptor.name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_DATA_OFFSET,
                data,
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_LENGTH_OFFSET,
                self._int64_literal(node.loc, source_type.length),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_CAPACITY_OFFSET,
                self._int64_literal(node.loc, source_type.length),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(node.loc, element_bytes),
                node.loc,
            ),
            self._store_i64_field(
                descriptor_word,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(node.loc, flags),
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

    def _lower_stack_array_declare(
        self,
        node: hir.Declare,
    ) -> list[hir.AST]:
        if not isinstance(node.expr, hir.ArrayLiteral):
            array_type = node.annotation or node.expr.type
            if not isinstance(array_type, ty.ArrayType) or array_type.length is None:
                raise TypeError(
                    'INTERNAL ERROR: stack-data array copy requires an exact length'
                )
            source_is_raw = self._array_use_representation(node.expr) is not None
            prelude, source = self._extract_expression(node.expr)
            element_bytes, _signed = self._array_element_layout(
                array_type.element,
                node,
            )
            target = hir.ExpressedIdentifier(
                node.loc,
                'int64',
                node.name,
                binding_id=node.binding_id,
            )
            statements: list[hir.AST] = [
                *prelude,
                replace(
                    node,
                    decltype='let',
                    annotation='int64',
                    expr=self._intrinsic_call(
                        '__alloca__',
                        [self._int64_literal(
                            node.loc,
                            max(1, array_type.length * element_bytes),
                        )],
                        'int64',
                        node.loc,
                    ),
                ),
            ]
            for index in range(array_type.length):
                source_address = (
                    self._pointer_element_address(
                        source,
                        index,
                        element_bytes,
                        node.loc,
                    )
                    if source_is_raw
                    else self._array_element_address(
                        source,
                        index,
                        array_type.element,
                        node.loc,
                    )
                )
                target_address = self._pointer_element_address(
                    target,
                    index,
                    element_bytes,
                    node.loc,
                )
                statements.extend(self._copy_array_element_between_addresses(
                    source_address,
                    target_address,
                    array_type.element,
                    node.loc,
                ))
            return statements
        array_type = node.expr.type
        if not isinstance(array_type, ty.ArrayType) or array_type.length is None:
            raise TypeError(
                'INTERNAL ERROR: stack-data array literal requires an exact length'
            )
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            node.expr,
        )
        target = hir.ExpressedIdentifier(
            node.loc,
            'int64',
            node.name,
            binding_id=node.binding_id,
        )
        statements: list[hir.AST] = [
            replace(
                node,
                decltype='let',
                annotation='int64',
                expr=self._intrinsic_call(
                    '__alloca__',
                    [
                        self._int64_literal(
                            node.loc,
                            array_type.length * element_bytes,
                        )
                    ],
                    'int64',
                    node.loc,
                ),
            )
        ]
        for index, item in enumerate(node.expr.items):
            item_prelude, value = self._array_storage_value(
                item,
                array_type.element,
            )
            statements.extend(item_prelude)
            address = self._pointer_element_address(
                target,
                index,
                element_bytes,
                item.loc,
            )
            statements.append(
                self._array_store(value, address, array_type.element, item.loc)
            )
        return statements

    def _lower_array_assign(self, node: hir.Assign) -> list[hir.AST]:
        """Rebind an array without making the target another name for the source."""

        if node.op != '=':
            self._target_error(node, f'array compound assignment `{node.op}`')
        array_type = node.target.type
        if not isinstance(array_type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: array assignment target lost its type')
        place_cell = (
            self.current_place_parameter_cells.get(node.target.binding_id)
            if node.target.binding_id is not None
            else None
        )
        if place_cell is not None:
            if array_type.length is None:
                self._target_error(
                    node,
                    'whole-array rebinding through a runtime-length place',
                )
            # The local parameter contains the descriptor for storage prepared by
            # the caller.  Replacing that descriptor with one allocated in this
            # function would leave the caller holding pointers into an expired
            # stack frame, so copy recursively into the existing storage tree.
            return self._write_array_result_value(
                replace(node.target, type='int64'),
                node.value,
                array_type,
            )
        if self._array_use_representation(node.target) == 'stack_data':
            prelude, copied = self._clone_array_to_raw(node.value, array_type)
        else:
            prelude, copied = self._independent_array_value(
                node.value,
                array_type,
            )
        assignment = replace(node, value=copied)
        return [*prelude, assignment]

    def _independent_array_value(
        self,
        node: hir.AST,
        array_type: ty.ArrayType,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Produce an independently mutable array value from one expression."""

        if self._array_expression_owns_fresh_storage(node):
            return self._extract_expression(node)
        return self._clone_array_value(node, array_type)

    def _clone_array_to_raw(
        self,
        node: hir.AST,
        array_type: ty.ArrayType,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Copy one exact array value into fresh descriptor-free stack data."""

        if array_type.length is None:
            self._target_error(node, 'value-copying a dynamic-length raw array')
        source_is_raw = self._array_use_representation(node) is not None
        source_prelude, source = self._extract_expression(node)
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            node,
        )
        name = self._new_array_name('copy_data')
        target = hir.ExpressedIdentifier(node.loc, 'int64', name)
        statements: list[hir.AST] = [
            *source_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                name,
                'int64',
                self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(
                        node.loc,
                        max(1, array_type.length * element_bytes),
                    )],
                    'int64',
                    node.loc,
                ),
            ),
        ]
        for index in range(array_type.length):
            source_address = (
                self._pointer_element_address(
                    source,
                    index,
                    element_bytes,
                    node.loc,
                )
                if source_is_raw
                else self._array_element_address(
                    source,
                    index,
                    array_type.element,
                    node.loc,
                )
            )
            target_address = self._pointer_element_address(
                target,
                index,
                element_bytes,
                node.loc,
            )
            statements.extend(self._copy_array_element_between_addresses(
                source_address,
                target_address,
                array_type.element,
                node.loc,
            ))
        return statements, target

    def _clone_array_value(
        self,
        node: hir.AST,
        array_type: ty.ArrayType,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Materialize a fresh array descriptor and recursively copied buffer."""

        if array_type.length is None:
            return self._clone_dynamic_array_value(node, array_type)
        source_is_raw = self._array_use_representation(node) is not None
        source_prelude, source = self._extract_expression(node)
        allocation, target = self._allocate_array_value(array_type, node.loc)
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            node,
        )
        statements = [*source_prelude, *allocation]
        descriptor = replace(target, type='int64')
        for index in range(array_type.length):
            source_address = (
                self._pointer_element_address(
                    source,
                    index,
                    element_bytes,
                    node.loc,
                )
                if source_is_raw
                else self._array_element_address(
                    source,
                    index,
                    array_type.element,
                    node.loc,
                )
            )
            target_address = self._array_element_address(
                descriptor,
                index,
                array_type.element,
                node.loc,
            )
            statements.extend(self._copy_array_element_between_addresses(
                source_address,
                target_address,
                array_type.element,
                node.loc,
            ))
        return statements, target

    def _arena_allocation(self, size: hir.AST, loc) -> hir.FunctionCall:
        """Allocate ``size`` bytes from the prelude's process arena."""
        function = next(
            (
                candidate
                for candidate in self.functions
                if candidate.logical_name.endswith('_arena_alloc')
            ),
            None,
        )
        if function is None:
            self._target_error(
                hir.Void(loc, ty.VOID_TYPE),
                'arena allocation without the prelude arena',
            )
        function_type = ty.FunctionType(
            [ty.PosOrKwArg(None, 'int64')],
            [],
            None,
            'int64',
        )
        return hir.FunctionCall(
            loc,
            'int64',
            hir.ExpressedIdentifier(loc, function_type, function.symbol),
            [size],
            {},
        )

    def _is_word_element(self, element: ty.Type) -> bool:
        """Elements copied as one word: scalars and immutable string handles."""
        return (
            element == 'bool'
            or ty.fixed_integer_layout(element) is not None
            or self._is_string_valued(element)
        )

    @classmethod
    def _is_word_element_static(cls, element: ty.Type) -> bool:
        """Elements copied as one word: scalars and immutable string handles."""
        return (
            element == 'bool'
            or ty.fixed_integer_layout(element) is not None
            or cls._is_string_valued(element)
        )

    def _array_grow_statements(
        self,
        descriptor: hir.AST,
        needed: hir.AST,
        element_type: ty.Type,
        element_bytes: int,
        loc,
    ) -> list[hir.AST]:
        """Ensure ``capacity >= needed``, moving the data into the arena.

        Growth doubles the capacity (minimum 8, at least ``needed``), copies
        the current elements into a fresh arena buffer, and repoints the
        descriptor, so raw stack, static, or borrowed data is never written
        through: the first growth always relocates.
        """
        capacity = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('capacity'))
        new_capacity = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('new_capacity'))
        old_data = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('old_data'))
        new_data = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('new_data'))
        index = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('grow_index'))
        length = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('grow_length'))

        def declare(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.Declare:
            return hir.Declare(loc, ty.VOID_TYPE, 'let', target.name, 'int64', value)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.Assign:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        def lt(left: hir.AST, right: hir.AST) -> hir.AST:
            return self._int64_comparison('__lt__', left, right, loc)

        copy_body = self._copy_array_element_between_addresses(
            self._pointer_element_address(old_data, index, element_bytes, loc),
            self._pointer_element_address(new_data, index, element_bytes, loc),
            element_type,
            loc,
        )
        copy_body.append(
            assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc))
        )
        grow = hir.Block(
            loc,
            ty.VOID_TYPE,
            [
                declare(new_capacity, self._int64_binary('__mul__', capacity, self._int64_literal(loc, 2), loc)),
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [hir.IfArm(loc, ty.VOID_TYPE, lt(new_capacity, needed), assign(new_capacity, needed))],
                    None,
                ),
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [hir.IfArm(loc, ty.VOID_TYPE, lt(new_capacity, self._int64_literal(loc, 8)), assign(new_capacity, self._int64_literal(loc, 8)))],
                    None,
                ),
                declare(old_data, self._load_i64_field(descriptor, ARRAY_DATA_OFFSET, loc)),
                declare(length, self._load_i64_field(descriptor, ARRAY_LENGTH_OFFSET, loc)),
                declare(
                    new_data,
                    self._arena_allocation(
                        self._int64_binary('__mul__', new_capacity, self._int64_literal(loc, element_bytes), loc),
                        loc,
                    ),
                ),
                declare(index, self._int64_literal(loc, 0)),
                hir.Flow(
                    loc,
                    ty.VOID_TYPE,
                    [hir.LoopArm(loc, ty.VOID_TYPE, lt(index, length), hir.Block(loc, ty.VOID_TYPE, copy_body, True))],
                    None,
                ),
                self._store_i64_field(descriptor, ARRAY_DATA_OFFSET, new_data, loc),
                self._store_i64_field(descriptor, ARRAY_CAPACITY_OFFSET, new_capacity, loc),
                self._store_i64_field(descriptor, ARRAY_FLAGS_OFFSET, self._int64_literal(loc, ARRAY_MUTABLE), loc),
            ],
            True,
        )
        return [
            declare(capacity, self._load_i64_field(descriptor, ARRAY_CAPACITY_OFFSET, loc)),
            hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, lt(capacity, needed), grow)], None),
        ]

    @staticmethod
    def _optional_method_argument(node: hir.FunctionCall, name: str) -> hir.AST | None:
        """The argument bound to an optional parameter, or None when it was left out.

        Call canonicalization lowers a missing optional argument to a placeholder
        value followed by a `false` presence flag (and a present one to the
        value followed by `true`), so the flag decides.
        """
        args = node.pos_args
        if len(args) >= 2 and isinstance(args[1], hir.Bool):
            return args[0] if args[1].value else None
        if args:
            return args[0]
        return node.kw_args.get(name)

    def _extract_array_method_call(
        self,
        node: hir.FunctionCall,
    ) -> tuple[list[hir.AST], hir.AST]:
        """Lower ``xs.push(v)``, ``xs.pop``/``xs.pop(idx)``, ``xs.insert(v idx)``, ``xs.truncate(n)``, ``xs.clear``, ``xs.reserve(n)``."""
        method = node.func
        assert isinstance(method, hir.ArrayMethod)
        array_type = method.array.type
        if not isinstance(array_type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: array method receiver is not an array')
        element_type = array_type.element
        if method.name == 'join':
            return self._join_string_array(node, method, array_type)
        if not self._is_word_element(element_type):
            self._target_error(node, 'growing an array whose elements are not word scalars or string handles')
        loc = node.loc
        prelude, descriptor = self._extract_expression(method.array)
        if isinstance(descriptor, hir.ExpressedIdentifier):
            descriptor = replace(descriptor, type='int64')
        element_bytes, _signed = self._array_element_layout(element_type, node)
        length = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('method_length'))
        length_declare = hir.Declare(
            loc, ty.VOID_TYPE, 'let', length.name, 'int64',
            self._load_i64_field(descriptor, ARRAY_LENGTH_OFFSET, loc),
        )
        data = self._load_i64_field(descriptor, ARRAY_DATA_OFFSET, loc)
        if method.name == 'push':
            value_prelude, value = self._extract_expression(node.pos_args[0])
            next_length = self._int64_binary('__add__', length, self._int64_literal(loc, 1), loc)
            return [
                *prelude,
                *value_prelude,
                length_declare,
                *self._array_grow_statements(descriptor, next_length, element_type, element_bytes, loc),
                self._array_store(
                    value,
                    self._pointer_element_address(data, length, element_bytes, loc),
                    element_type,
                    loc,
                ),
            ], self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, next_length, loc)
        one = self._int64_literal(loc, 1)

        def shift_loop(cursor_start: hir.AST, condition_name: str, bound: hir.AST, source_delta: int, step: int) -> list[hir.AST]:
            # Move elements one slot: `loop cursor <op> bound { xs[cursor] = xs[cursor + delta]; cursor += step }`
            cursor = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('shift'))
            source_index = self._int64_binary('__add__' if source_delta > 0 else '__sub__', cursor, one, loc)
            body = hir.Block(loc, ty.VOID_TYPE, [
                self._array_store(
                    self._array_load(self._pointer_element_address(data, source_index, element_bytes, loc), element_type, loc),
                    self._pointer_element_address(data, cursor, element_bytes, loc),
                    element_type,
                    loc,
                ),
                hir.Assign(loc, ty.VOID_TYPE, cursor, '=', self._int64_binary('__add__' if step > 0 else '__sub__', cursor, one, loc)),
            ], True)
            return [
                hir.Declare(loc, ty.VOID_TYPE, 'let', cursor.name, 'int64', cursor_start),
                hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(loc, ty.VOID_TYPE, self._int64_comparison(condition_name, cursor, bound, loc), body)], None),
            ]

        if method.name == 'pop':
            last = self._int64_binary('__sub__', length, one, loc)
            result = hir.ExpressedIdentifier(loc, element_type, self._new_array_name('popped'))
            index_arg = self._optional_method_argument(node, 'idx')
            if index_arg is None:
                return [
                    *prelude,
                    length_declare,
                    hir.Declare(
                        loc, ty.VOID_TYPE, 'let', result.name, element_type,
                        self._array_load(
                            self._pointer_element_address(data, last, element_bytes, loc),
                            element_type,
                            loc,
                        ),
                    ),
                    self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, last, loc),
                ], result
            # `xs.pop(idx)`: take the element, shift the tail down, shrink
            index_prelude, index = self._extract_expression(index_arg)
            index_name = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('pop_index'))
            last_name = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('last'))
            return [
                *prelude,
                *index_prelude,
                length_declare,
                hir.Declare(loc, ty.VOID_TYPE, 'let', index_name.name, 'int64', index),
                hir.Declare(loc, ty.VOID_TYPE, 'let', last_name.name, 'int64', last),
                hir.Declare(
                    loc, ty.VOID_TYPE, 'let', result.name, element_type,
                    self._array_load(
                        self._pointer_element_address(data, index_name, element_bytes, loc),
                        element_type,
                        loc,
                    ),
                ),
                *shift_loop(index_name, '__lt__', last_name, +1, +1),
                self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, last_name, loc),
            ], result
        if method.name == 'insert':
            # grow, shift the tail up from the end, store, extend
            value_prelude, value = self._extract_expression(node.pos_args[0])
            index_arg = node.pos_args[1] if len(node.pos_args) > 1 else node.kw_args['idx']
            index_prelude, index = self._extract_expression(index_arg)
            index_name = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('insert_index'))
            next_length = self._int64_binary('__add__', length, one, loc)
            return [
                *prelude,
                *value_prelude,
                *index_prelude,
                length_declare,
                hir.Declare(loc, ty.VOID_TYPE, 'let', index_name.name, 'int64', index),
                *self._array_grow_statements(descriptor, next_length, element_type, element_bytes, loc),
                *shift_loop(length, '__gt__', index_name, -1, -1),
                self._array_store(
                    value,
                    self._pointer_element_address(data, index_name, element_bytes, loc),
                    element_type,
                    loc,
                ),
            ], self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, next_length, loc)
        if method.name == 'truncate':
            count_prelude, count = self._extract_expression(node.pos_args[0] if node.pos_args else node.kw_args['count'])
            count_name = hir.ExpressedIdentifier(loc, 'int64', self._new_array_name('truncate_to'))
            return [
                *prelude,
                *count_prelude,
                length_declare,
                hir.Declare(loc, ty.VOID_TYPE, 'let', count_name.name, 'int64', count),
                hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                    loc, ty.VOID_TYPE,
                    self._int64_comparison('__lt__', count_name, length, loc),
                    self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, count_name, loc),
                )], None),
            ], hir.Void(loc, ty.VOID_TYPE)
        if method.name == 'clear':
            return [*prelude], self._store_i64_field(
                descriptor, ARRAY_LENGTH_OFFSET, self._int64_literal(loc, 0), loc
            )
        if method.name == 'sort':
            return [*prelude, length_declare, *self._array_sort_statements(
                descriptor, data, length, element_type, element_bytes, node, loc,
            )], hir.Void(loc, ty.VOID_TYPE)
        if method.name == 'reserve':
            count_prelude, count = self._extract_expression(node.pos_args[0])
            return [
                *prelude,
                *count_prelude,
                *self._array_grow_statements(descriptor, count, element_type, element_bytes, loc),
            ], hir.Void(loc, ty.VOID_TYPE)
        self._target_error(node, f'array method `{method.name}`')

    SORT_SMALL_LIMIT = 32

    def _array_sort_statements(
        self,
        descriptor: hir.AST,
        data: hir.AST,
        length: hir.AST,
        element_type: ty.Type,
        element_bytes: int,
        node: hir.AST,
        loc: Span,
    ) -> list[hir.AST]:
        """In-place ascending sort of fixed-width integer elements.

        Dispatch by length: at most ``SORT_SMALL_LIMIT`` elements use an
        insertion sort; longer arrays use an LSD radix sort over 8-bit digits
        (one pass per element byte) with an arena-allocated swap buffer. Keys
        are the element's bit pattern with the sign bit flipped for signed
        types, so the order is numeric for every width. This is the seed of
        the planned dispatcher: comparison sorts join it when comparators and
        non-integer elements arrive.
        """
        _, signed = self._array_element_layout(element_type, node)
        bits = element_bytes * 8
        one = self._int64_literal(loc, 1)
        zero = self._int64_literal(loc, 0)
        word_ops = ty.FunctionType(
            [ty.PosOrKwArg('left', 'uint64'), ty.PosOrKwArg('right', 'uint64')], [], None, 'uint64', [],
        )
        compare_type = ty.FunctionType(
            [ty.PosOrKwArg('left', element_type), ty.PosOrKwArg('right', element_type)], [], None, 'bool', [],
        )

        def word(name: str, left: hir.AST, right: hir.AST) -> hir.FunctionCall:
            return hir.FunctionCall(loc, 'uint64', hir.ExpressedIdentifier(loc, word_ops, name), [left, right], {})

        def greater(left: hir.AST, right: hir.AST) -> hir.FunctionCall:
            return hir.FunctionCall(loc, 'bool', hir.ExpressedIdentifier(loc, compare_type, '__gt__'), [left, right], {})

        def name(role: str) -> hir.ExpressedIdentifier:
            return hir.ExpressedIdentifier(loc, 'int64', self._new_array_name(role))

        def declare(identifier: hir.ExpressedIdentifier, value: hir.AST, type_: ty.Type = 'int64') -> hir.Declare:
            return hir.Declare(loc, ty.VOID_TYPE, 'let', identifier.name, type_, value)

        def assign(identifier: hir.ExpressedIdentifier, value: hir.AST) -> hir.Assign:
            return hir.Assign(loc, ty.VOID_TYPE, identifier, '=', value)

        def add(left: hir.AST, right: hir.AST) -> hir.AST:
            return self._int64_binary('__add__', left, right, loc)

        def counting_loop(role: str, limit: hir.AST, body_of) -> list[hir.AST]:
            # a fresh counter per loop: udewy forbids redeclaring a name in one scope
            counter = name(role)
            return [
                declare(counter, zero),
                hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
                    loc, ty.VOID_TYPE, self._int64_comparison('__lt__', counter, limit, loc),
                    hir.Block(loc, ty.VOID_TYPE, [*body_of(counter), assign(counter, add(counter, one))], True),
                )], None),
            ]

        def load_word(address: hir.AST) -> hir.AST:
            return self._intrinsic_call('__load_i64__', [address], 'int64', loc)

        def store_word(value: hir.AST, address: hir.AST) -> hir.AST:
            return self._intrinsic_call('__store_i64__', [value, address], ty.VOID_TYPE, loc)

        def element_at(base: hir.AST, index: hir.AST) -> hir.AST:
            return self._pointer_element_address(base, index, element_bytes, loc)

        def key_of(value: hir.AST) -> hir.AST:
            # numeric order as an unsigned bit pattern of the element's width
            key: hir.AST = hir.Transmute(loc, 'uint64', value)
            if signed:
                key = word('__xor__', key, hir.Integer(loc, 'uint64', '0d', 1 << (bits - 1)))
            if bits < 64:
                key = word('__and__', key, hir.Integer(loc, 'uint64', '0d', (1 << bits) - 1))
            return key

        # --- insertion sort for short arrays ---
        outer, inner = name('sort_i'), name('sort_j')
        key = hir.ExpressedIdentifier(loc, element_type, self._new_array_name('sort_key'))
        previous = self._int64_binary('__sub__', inner, one, loc)
        insertion = [
            declare(outer, one),
            hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
                loc, ty.VOID_TYPE, self._int64_comparison('__lt__', outer, length, loc),
                hir.Block(loc, ty.VOID_TYPE, [
                    declare(key, self._array_load(element_at(data, outer), element_type, loc), element_type),
                    declare(inner, outer),
                    hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
                        loc, ty.VOID_TYPE,
                        hir.ShortCircuit(
                            loc, 'bool', 'and',
                            self._int64_comparison('__gt__', inner, zero, loc),
                            greater(self._array_load(element_at(data, previous), element_type, loc), key),
                        ),
                        hir.Block(loc, ty.VOID_TYPE, [
                            self._array_store(self._array_load(element_at(data, previous), element_type, loc), element_at(data, inner), element_type, loc),
                            assign(inner, previous),
                        ], True),
                    )], None),
                    self._array_store(key, element_at(data, inner), element_type, loc),
                    assign(outer, add(outer, one)),
                ], True),
            )], None),
        ]

        # --- LSD radix sort for longer arrays ---
        counts, buffer, source, target, swap = name('sort_counts'), name('sort_buffer'), name('sort_src'), name('sort_dst'), name('sort_swap')
        total = name('sort_total')

        def bucket_address(digit: hir.AST) -> hir.AST:
            return add(counts, self._int64_binary('__mul__', digit, self._int64_literal(loc, 8), loc))

        element = hir.ExpressedIdentifier(loc, element_type, self._new_array_name('sort_elem'))
        digit = name('sort_digit')
        slot = name('sort_slot')
        position = name('sort_pos')

        def one_pass(digit_pass: hir.ExpressedIdentifier) -> list[hir.AST]:
            shift = self._int64_binary('__mul__', digit_pass, self._int64_literal(loc, 8), loc)

            def digit_of(value: hir.AST) -> hir.AST:
                shifted = word('__rshift__', key_of(value), hir.Transmute(loc, 'uint64', shift))
                return hir.Transmute(loc, 'int64', word('__and__', shifted, hir.Integer(loc, 'uint64', '0d', 255)))

            return [
                *counting_loop('sort_bucket', self._int64_literal(loc, 256), lambda bucket: [store_word(zero, bucket_address(bucket))]),
                *counting_loop('sort_index', length, lambda index: [
                    declare(digit, digit_of(self._array_load(element_at(source, index), element_type, loc))),
                    declare(slot, bucket_address(digit)),
                    store_word(add(load_word(slot), one), slot),
                ]),
                declare(total, zero),
                *counting_loop('sort_bucket', self._int64_literal(loc, 256), lambda bucket: [
                    declare(slot, bucket_address(bucket)),
                    declare(position, load_word(slot)),
                    store_word(total, slot),
                    assign(total, add(total, position)),
                ]),
                *counting_loop('sort_index', length, lambda index: [
                    declare(element, self._array_load(element_at(source, index), element_type, loc), element_type),
                    declare(digit, digit_of(element)),
                    declare(slot, bucket_address(digit)),
                    declare(position, load_word(slot)),
                    self._array_store(element, element_at(target, position), element_type, loc),
                    store_word(add(position, one), slot),
                ]),
                declare(swap, source),
                assign(source, target),
                assign(target, swap),
            ]

        radix = [
            declare(counts, self._intrinsic_call('__alloca__', [self._int64_literal(loc, 256 * 8)], 'int64', loc)),
            declare(buffer, self._arena_allocation(self._int64_binary('__mul__', length, self._int64_literal(loc, element_bytes), loc), loc)),
            declare(source, data),
            declare(target, buffer),
            *counting_loop('sort_pass', self._int64_literal(loc, element_bytes), one_pass),
        ]
        if element_bytes % 2 == 1:
            # an odd number of passes leaves the result in the buffer
            radix.extend(counting_loop('sort_index', length, lambda index: [
                self._array_store(self._array_load(element_at(source, index), element_type, loc), element_at(data, index), element_type, loc),
            ]))
        return [
            hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(
                loc, ty.VOID_TYPE,
                self._int64_comparison('__le__', length, self._int64_literal(loc, self.SORT_SMALL_LIMIT), loc),
                hir.Block(loc, ty.VOID_TYPE, insertion, True),
            )], hir.Block(loc, ty.VOID_TYPE, radix, True)),
        ]

    def _dynamic_array_result_write(self, item: hir.AST) -> list[hir.AST]:
        """Return a runtime-length array as an arena-backed descriptor."""
        array_type = self.current_dynamic_array_result
        if array_type is None:
            raise TypeError('INTERNAL ERROR: missing dynamic array result type')
        source = item
        while (
            isinstance(source, hir.Block)
            and not source.scoped
            and len(source.items) == 1
        ):
            source = source.items[0]
        if (
            isinstance(source, hir.FunctionCall)
            and isinstance(source.type, ty.ArrayType)
            and source.type.length is None
        ):
            # Runtime-length call results are already arena-backed.
            prelude, value = self._extract_expression(source)
            return [*prelude, hir.Return(item.loc, ty.BOTTOM_TYPE, replace(value, type='int64'))]
        prelude, copied = self._clone_dynamic_array_value(
            item,
            array_type,
            arena=True,
        )
        return [*prelude, hir.Return(item.loc, ty.BOTTOM_TYPE, replace(copied, type='int64'))]

    def _clone_dynamic_array_value(
        self,
        node: hir.AST,
        array_type: ty.ArrayType,
        *,
        arena: bool = False,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Copy a descriptor-backed runtime-length array.

        Storage comes from the current frame, or from the process arena when
        ``arena`` is set so the copy may outlive the frame.
        """

        if self.lowering_module_startup and not arena:
            # module-level storage lives for the whole process: the arena is
            # the right home for a copy made during startup
            arena = True
        if arena:
            element = array_type.element
            if not self._is_word_element(element):
                self._target_error(
                    node,
                    'an arena-backed array whose elements are not word scalars or string handles',
                )
        source_prelude, source = self._extract_expression(node)
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            node,
        )
        length_name = self._new_array_name('copy_length')
        length = hir.ExpressedIdentifier(node.loc, 'int64', length_name)
        data_name = self._new_array_name('copy_data')
        data = hir.ExpressedIdentifier(node.loc, 'int64', data_name)
        target = self._new_array_temp(node)
        descriptor = replace(target, type='int64')
        index_name = self._new_array_name('copy_index')
        index = hir.ExpressedIdentifier(node.loc, 'int64', index_name)
        allocation_bytes: hir.AST = length
        if element_bytes != 1:
            allocation_bytes = self._int64_binary(
                '__mul__',
                length,
                self._int64_literal(node.loc, element_bytes),
                node.loc,
            )
        source_address = self._array_element_address(
            source,
            index,
            array_type.element,
            node.loc,
        )
        target_address = self._pointer_element_address(
            data,
            index,
            element_bytes,
            node.loc,
        )
        copy_body = self._copy_array_element_between_addresses(
            source_address,
            target_address,
            array_type.element,
            node.loc,
        )
        copy_body.append(hir.Assign(
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
        ))
        copy_loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    node.loc,
                    ty.VOID_TYPE,
                    self._int64_comparison(
                        '__lt__',
                        index,
                        length,
                        node.loc,
                    ),
                    hir.Block(node.loc, ty.VOID_TYPE, copy_body, True),
                )
            ],
            None,
        )
        statements: list[hir.AST] = [
            *source_prelude,
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                length_name,
                'int64',
                self._load_i64_field(source, ARRAY_LENGTH_OFFSET, node.loc),
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._arena_allocation(allocation_bytes, node.loc)
                if arena
                else self._intrinsic_call(
                    '__alloca__',
                    [allocation_bytes],
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
                self._arena_allocation(
                    self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE), node.loc
                )
                if arena
                else self._intrinsic_call(
                    '__alloca__',
                    [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    node.loc,
                ),
            ),
            self._store_i64_field(descriptor, ARRAY_DATA_OFFSET, data, node.loc),
            self._store_i64_field(
                descriptor,
                ARRAY_LENGTH_OFFSET,
                length,
                node.loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_CAPACITY_OFFSET,
                length,
                node.loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(node.loc, element_bytes),
                node.loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(node.loc, ARRAY_MUTABLE),
                node.loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_OWNER_OFFSET,
                self._int64_literal(node.loc, 0),
                node.loc,
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                index_name,
                'int64',
                self._int64_literal(node.loc, 0),
            ),
            copy_loop,
        ]
        return statements, target

    def _extract_array_literal(
        self,
        node: hir.ArrayLiteral,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate fresh backing storage and initialize one array value."""

        if any(isinstance(item, hir.Spread) for item in node.items):
            return self._extract_spread_array_literal(node)
        if not isinstance(node.type, ty.ArrayType) or node.type.length is None:
            self._target_error(node, 'array literal does not have an exact layout')
        if self.lowering_module_startup and not all(
            self._module_array_item_is_stable(item, set())
            for item in node.items
        ):
            self._target_error(
                node,
                'top-level arrays currently require compile-time-stable elements',
            )
        statements, target = self._allocate_array_value(node.type, node.loc)
        for index, item in enumerate(node.items):
            item_prelude, value = self._array_storage_value(
                item,
                node.type.element,
            )
            statements.extend(item_prelude)
            address = self._array_element_address(
                replace(target, type='int64'),
                index,
                node.type.element,
                item.loc,
            )
            statements.append(
                self._array_store(value, address, node.type.element, item.loc)
            )
        return statements, target

    def _extract_spread_array_literal(
        self,
        node: hir.ArrayLiteral,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """`[xs... 0 ys...]`: sum the lengths, allocate once (the frame for an
        exact length, the arena for a runtime length), then copy element by
        element behind a running cursor."""
        if not isinstance(node.type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: spread literal is not an array')
        if self.lowering_module_startup:
            self._target_error(node, 'a top-level array literal with a spread')
        loc = node.loc
        element = node.type.element
        element_bytes, _signed = self._array_element_layout(element, node)
        statements: list[hir.AST] = []

        def declare(role: str, value: hir.AST) -> hir.ExpressedIdentifier:
            name = self._new_array_name(role)
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', name, 'int64', value))
            return hir.ExpressedIdentifier(loc, 'int64', name)

        def assign(target: hir.ExpressedIdentifier, value: hir.AST) -> hir.AST:
            return hir.Assign(loc, ty.VOID_TYPE, target, '=', value)

        # sources first (once each), then the total length
        sources: list[hir.AST | None] = []
        total: hir.AST = self._int64_literal(loc, sum(1 for item in node.items if not isinstance(item, hir.Spread)))
        for item in node.items:
            if not isinstance(item, hir.Spread):
                sources.append(None)
                continue
            prelude, source = self._extract_expression(item.value)
            statements.extend(prelude)
            held = declare('spread_source', replace(source, type='int64') if isinstance(source, hir.ExpressedIdentifier) else source)
            sources.append(held)
            total = self._int64_binary('__add__', total, self._load_i64_field(held, ARRAY_LENGTH_OFFSET, loc), loc)
        length = declare('spread_length', total)
        if node.type.length is not None:
            allocation, target = self._allocate_array_value(node.type, loc)
            statements.extend(allocation)
            descriptor = replace(target, type='int64')
        else:
            bytes_needed: hir.AST = length if element_bytes == 1 else self._int64_binary('__mul__', length, self._int64_literal(loc, element_bytes), loc)
            data = declare('spread_data', self._arena_allocation(bytes_needed, loc))
            target = self._new_array_temp(node)
            descriptor = replace(target, type='int64')
            statements.extend([
                hir.Declare(loc, ty.VOID_TYPE, 'let', target.name, 'int64', self._arena_allocation(self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE), loc)),
                self._store_i64_field(descriptor, ARRAY_DATA_OFFSET, data, loc),
                self._store_i64_field(descriptor, ARRAY_LENGTH_OFFSET, length, loc),
                self._store_i64_field(descriptor, ARRAY_CAPACITY_OFFSET, length, loc),
                self._store_i64_field(descriptor, ARRAY_STRIDE_OFFSET, self._int64_literal(loc, element_bytes), loc),
                self._store_i64_field(descriptor, ARRAY_FLAGS_OFFSET, self._int64_literal(loc, ARRAY_MUTABLE), loc),
                self._store_i64_field(descriptor, ARRAY_OWNER_OFFSET, self._int64_literal(loc, 0), loc),
            ])
        data_pointer = self._load_i64_field(descriptor, ARRAY_DATA_OFFSET, loc)
        cursor = declare('spread_cursor', self._int64_literal(loc, 0))
        for item, source in zip(node.items, sources):
            if source is None:
                item_prelude, value = self._array_storage_value(item, element)
                statements.extend(item_prelude)
                statements.append(self._array_store(value, self._pointer_element_address(data_pointer, cursor, element_bytes, loc), element, item.loc))
                statements.append(assign(cursor, self._int64_binary('__add__', cursor, self._int64_literal(loc, 1), loc)))
                continue
            index = declare('spread_index', self._int64_literal(loc, 0))
            count = self._load_i64_field(source, ARRAY_LENGTH_OFFSET, loc)
            body = self._copy_array_element_between_addresses(
                self._array_element_address(source, index, element, loc),
                self._pointer_element_address(data_pointer, cursor, element_bytes, loc),
                element,
                loc,
            )
            body.extend([
                assign(index, self._int64_binary('__add__', index, self._int64_literal(loc, 1), loc)),
                assign(cursor, self._int64_binary('__add__', cursor, self._int64_literal(loc, 1), loc)),
            ])
            statements.append(hir.Flow(loc, ty.VOID_TYPE, [hir.LoopArm(
                loc, ty.VOID_TYPE, self._int64_comparison('__lt__', index, count, loc), hir.Block(loc, ty.VOID_TYPE, body, True),
            )], None))
        return statements, target

    def _allocate_array_value(
        self,
        array_type: ty.ArrayType,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate an exact array descriptor and its caller-owned backing data."""

        if array_type.length is None:
            self._target_error(
                hir.Void(loc, ty.VOID_TYPE),
                'array allocation requires an exact compile-time length',
            )
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            hir.Void(loc, ty.VOID_TYPE),
        )
        target = self._new_array_temp(hir.Void(loc, array_type))
        data_name = self._new_array_name('data')
        data = hir.ExpressedIdentifier(loc, 'int64', data_name)
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        descriptor = replace(target, type='int64')
        statements: list[hir.AST] = [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(
                        loc,
                        max(1, array_type.length * element_bytes),
                    )],
                    'int64',
                    loc,
                ),
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                self._intrinsic_call(
                    allocator,
                    [self._int64_literal(loc, ARRAY_DESCRIPTOR_SIZE)],
                    'int64',
                    loc,
                ),
            ),
            self._store_i64_field(descriptor, ARRAY_DATA_OFFSET, data, loc),
            self._store_i64_field(
                descriptor,
                ARRAY_LENGTH_OFFSET,
                self._int64_literal(loc, array_type.length),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_CAPACITY_OFFSET,
                self._int64_literal(loc, array_type.length),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_STRIDE_OFFSET,
                self._int64_literal(loc, element_bytes),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_FLAGS_OFFSET,
                self._int64_literal(loc, ARRAY_MUTABLE),
                loc,
            ),
            self._store_i64_field(
                descriptor,
                ARRAY_OWNER_OFFSET,
                self._int64_literal(loc, 0),
                loc,
            ),
        ]
        return statements, target

    def _allocate_array_result_value(
        self,
        array_type: ty.ArrayType,
        loc: Span,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate the complete exact array storage tree in the caller."""

        statements, target = self._allocate_array_value(array_type, loc)
        descriptor = replace(target, type='int64')
        for index in range(array_type.length or 0):
            address = self._array_element_address(
                descriptor,
                index,
                array_type.element,
                loc,
            )
            if isinstance(array_type.element, ty.ArrayType):
                nested_statements, nested = self._allocate_array_result_value(
                    array_type.element,
                    loc,
                )
                statements.extend(nested_statements)
                statements.append(
                    self._array_store(nested, address, array_type.element, loc)
                )
            elif isinstance(array_type.element, ty.ObjectType):
                nested_statements, nested = self._allocate_object_result_value(
                    array_type.element,
                    loc,
                )
                statements.extend(nested_statements)
                statements.append(
                    self._array_store(nested, address, array_type.element, loc)
                )
        return statements, target

    def _array_storage_value(
        self,
        node: hir.AST,
        element_type: ty.Type,
    ) -> tuple[list[hir.AST], hir.AST]:
        if isinstance(node.type, ty.IntegerLiteralType):
            return [], hir.Integer(
                node.loc,
                element_type,
                t0.base10,
                node.type.value,
            )
        if isinstance(element_type, ty.ArrayType):
            return self._independent_array_value(node, element_type)
        if isinstance(element_type, ty.ObjectType):
            return self._independent_object_value(node, element_type)
        return self._extract_expression(node)

    def _copy_array_element_between_addresses(
        self,
        source_address: hir.AST,
        target_address: hir.AST,
        element_type: ty.Type,
        loc: Span,
    ) -> list[hir.AST]:
        """Copy one stored element, recursively materializing mutable values."""

        source_value = self._array_load(source_address, element_type, loc)
        if isinstance(element_type, ty.ArrayType):
            prelude, copied = self._clone_array_value(
                replace(source_value, type='int64'),
                element_type,
            )
        elif isinstance(element_type, ty.ObjectType):
            prelude, copied = self._clone_object_value(
                replace(source_value, type='int64'),
                element_type,
            )
        else:
            prelude, copied = [], source_value
        return [
            *prelude,
            self._array_store(copied, target_address, element_type, loc),
        ]

    def _module_array_item_is_stable(
        self,
        node: hir.AST,
        seen: set[int],
    ) -> bool:
        """Whether a top-level array element is a compile-time integer value."""

        if isinstance(node, (hir.Integer, hir.String, hir.BasedString)):
            return True
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            return self._module_array_item_is_stable(node.expr, seen)
        if isinstance(node, hir.ExpressedIdentifier):
            binding = self.identifier_bindings.get(id(node))
            if (
                binding is None
                or binding.order in seen
                or binding.expr is None
            ):
                return False
            return self._module_array_item_is_stable(
                binding.expr,
                {*seen, binding.order},
            )
        if (
            isinstance(node, hir.FunctionCall)
            and isinstance(node.func, hir.ExpressedIdentifier)
            and node.func.name in {
                '__unary_sub__',
                '__not__',
                '__add__',
                '__sub__',
                '__mul__',
                '__floordiv__',
                '__mod__',
                '__lshift__',
                '__rshift__',
            }
        ):
            return all(
                self._module_array_item_is_stable(arg, seen)
                for arg in node.pos_args
            )
        return False

    def _new_array_temp(self, node: hir.AST) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_array_{self.next_array_temp}'
            self.next_array_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, node.type, name)

    def _new_array_name(self, role: str) -> str:
        while True:
            name = f'__dewy_array_{role}_{self.next_array_temp}'
            self.next_array_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    def _array_element_layout(
        self,
        element_type: ty.Type,
        node: hir.AST,
    ) -> tuple[int, bool]:
        if element_type == 'bool':
            return 1, False
        layout = ty.fixed_integer_layout(element_type)
        if layout is not None:
            width, signed = layout
            return width // 8, signed
        if isinstance(
            element_type,
            (
                ty.ArrayType,
                ty.FunctionType,
                ty.ObjectType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(element_type, str)
            and element_type in {'string', 'grapheme', 'char'}
        ):
            return 8, True
        self._target_error(
            node,
            f'array element layout `{type_to_dewy(element_type)}`',
        )

    @classmethod
    def _array_result_elements_are_returnable(
        cls,
        array_type: ty.ArrayType,
    ) -> bool:
        """Whether callers can prepare the complete mutable result layout.

        Runtime-length arrays with word elements are returnable as *fields*:
        the caller holds a handle slot and the callee fills it with an
        arena-backed copy (see ``_arena_array_field_value``).
        """

        if array_type.length is None:
            return cls._is_word_element_static(array_type.element)
        element_type = array_type.element
        return (
            array_type.length == 0
            or element_type == 'bool'
            or ty.fixed_integer_layout(element_type) is not None
            or isinstance(element_type, ty.FunctionType)
            or (
                isinstance(element_type, ty.ArrayType)
                and cls._array_result_elements_are_returnable(element_type)
            )
            or (
                isinstance(element_type, ty.ObjectType)
                and cls._object_result_fields_are_returnable(element_type)
            )
        )

    def _array_element_address(
        self,
        array: hir.AST,
        index: int | hir.AST,
        element_type: ty.Type,
        loc: Span,
    ) -> hir.AST:
        element_bytes, _signed = self._array_element_layout(element_type, array)
        data = self._load_i64_field(array, ARRAY_DATA_OFFSET, loc)
        return self._pointer_element_address(data, index, element_bytes, loc)

    def _pointer_element_address(
        self,
        data: hir.AST,
        index: int | hir.AST,
        element_bytes: int,
        loc: Span,
    ) -> hir.AST:
        if isinstance(index, int):
            offset: hir.AST | int = index * element_bytes
            if offset == 0:
                return data
            offset = self._int64_literal(loc, offset)
        else:
            offset = index
            if element_bytes != 1:
                offset = self._int64_binary(
                    '__mul__',
                    offset,
                    self._int64_literal(loc, element_bytes),
                    loc,
                )
        return self._int64_binary(
            '__add__',
            data,
            offset,
            loc,
        )

    def _array_load(
        self,
        address: hir.AST,
        element_type: ty.Type,
        loc: Span,
    ) -> hir.AST:
        if element_type == 'bool':
            loaded = self._intrinsic_call('__load_u8__', [address], 'uint8', loc)
            return hir.Transmute(loc, 'bool', loaded)
        layout = ty.fixed_integer_layout(element_type)
        if layout is None:
            loaded = self._intrinsic_call('__load_i64__', [address], 'int64', loc)
            return replace(loaded, type=element_type)
        width, signed = layout
        prefix = 'i' if signed else 'u'
        return self._intrinsic_call(
            f'__load_{prefix}{width}__',
            [address],
            element_type,
            loc,
        )

    def _array_store(
        self,
        value: hir.AST,
        address: hir.AST,
        element_type: ty.Type,
        loc: Span,
    ) -> hir.FunctionCall:
        if element_type == 'bool':
            return self._intrinsic_call(
                '__store_u8__',
                [hir.Transmute(loc, 'uint8', value), address],
                ty.VOID_TYPE,
                loc,
            )
        layout = ty.fixed_integer_layout(element_type)
        if layout is None:
            if isinstance(element_type, ty.FunctionType):
                value = hir.Transmute(loc, 'int64', value)
            return self._intrinsic_call(
                '__store_i64__',
                [value, address],
                ty.VOID_TYPE,
                loc,
            )
        width, signed = layout
        prefix = 'i' if signed else 'u'
        return self._intrinsic_call(
            f'__store_{prefix}{width}__',
            [value, address],
            ty.VOID_TYPE,
            loc,
        )

    def _ensure_mutable_byte_array(
        self,
        descriptor: hir.AST,
        loc: Span,
    ) -> list[hir.AST]:
        flags = self._load_i64_field(descriptor, ARRAY_FLAGS_OFFSET, loc)
        borrowed = self._typed_equality(
            flags,
            self._int64_literal(loc, ARRAY_BORROWED_STATIC),
            'int64',
            loc,
        )
        length = self._load_i64_field(descriptor, ARRAY_LENGTH_OFFSET, loc)
        old_data = self._load_i64_field(descriptor, ARRAY_DATA_OFFSET, loc)
        data_name = self._new_array_name('cow_data')
        index_name = self._new_array_name('cow_index')
        data = hir.ExpressedIdentifier(loc, 'int64', data_name)
        index = hir.ExpressedIdentifier(loc, 'int64', index_name)
        allocation = self._intrinsic_call(
            '__alloca__',
            [length],
            'int64',
            loc,
        )
        source_address = self._int64_binary('__add__', old_data, index, loc)
        target_address = self._int64_binary('__add__', data, index, loc)
        byte = self._intrinsic_call(
            '__load_u8__',
            [source_address],
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
                    self._int64_comparison('__lt__', index, length, loc),
                    hir.Block(
                        loc,
                        ty.VOID_TYPE,
                        [
                            self._intrinsic_call(
                                '__store_u8__',
                                [byte, target_address],
                                ty.VOID_TYPE,
                                loc,
                            ),
                            hir.Assign(
                                loc,
                                ty.VOID_TYPE,
                                index,
                                '=',
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
        body = hir.Block(
            loc,
            ty.VOID_TYPE,
            [
                hir.Declare(
                    loc,
                    ty.VOID_TYPE,
                    'let',
                    data_name,
                    'int64',
                    allocation,
                ),
                hir.Declare(
                    loc,
                    ty.VOID_TYPE,
                    'let',
                    index_name,
                    'int64',
                    self._int64_literal(loc, 0),
                ),
                copy_loop,
                self._store_i64_field(
                    descriptor,
                    ARRAY_DATA_OFFSET,
                    data,
                    loc,
                ),
                self._store_i64_field(
                    descriptor,
                    ARRAY_CAPACITY_OFFSET,
                    length,
                    loc,
                ),
                self._store_i64_field(
                    descriptor,
                    ARRAY_FLAGS_OFFSET,
                    self._int64_literal(loc, ARRAY_MUTABLE),
                    loc,
                ),
                self._store_i64_field(
                    descriptor,
                    ARRAY_OWNER_OFFSET,
                    self._int64_literal(loc, 0),
                    loc,
                ),
            ],
            True,
        )
        return [hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, borrowed, body)])]

    def _finish_array_call(
        self,
        node: hir.FunctionCall,
        func: hir.AST,
        pos_args: list[hir.AST],
        kw_args: dict[str, hir.AST],
        prelude: list[hir.AST],
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if not isinstance(node.type, ty.ArrayType) or node.type.length is None:
            self._target_error(
                node,
                'array call results require an exact compile-time length',
            )
        result = self.array_result_destinations.pop(id(node), None)
        if result is None:
            allocation, result = self._allocate_array_result_value(
                node.type,
                node.loc,
            )
            prelude.extend(allocation)
        prelude.append(
            replace(
                node,
                type=ty.VOID_TYPE,
                func=func,
                pos_args=[*pos_args, replace(result, type='int64')],
                kw_args=kw_args,
            )
        )
        return prelude, result

    def _array_result_write(self, item: hir.AST) -> list[hir.AST]:
        """Copy one exact-length array result into storage owned by the caller."""

        if self.current_array_result is None:
            raise TypeError('INTERNAL ERROR: missing array result cell')
        array_type = self.current_array_result.type
        if not isinstance(array_type, ty.ArrayType) or array_type.length is None:
            raise TypeError(
                'INTERNAL ERROR: array result does not have an exact layout'
            )
        dest = replace(self.current_array_result, type='int64')
        return [
            *self._write_array_result_value(dest, item, array_type),
            hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
        ]

    def _write_array_result_value(
        self,
        dest: hir.AST,
        item: hir.AST,
        array_type: ty.ArrayType,
    ) -> list[hir.AST]:
        """Write an exact array into a complete storage tree owned by the caller."""

        if isinstance(item, hir.FunctionCall):
            destination_prelude, destination = self._result_destination_identifier(
                dest,
                array_type,
                item.loc,
                object_result=False,
            )
            self.array_result_destinations[id(item)] = destination
            prelude, result = self._extract_expression(item)
            if id(item) in self.array_result_destinations:
                del self.array_result_destinations[id(item)]
                raise TypeError(
                    'INTERNAL ERROR: array result destination was not consumed'
                )
            if (
                not isinstance(result, hir.ExpressedIdentifier)
                or result.name != destination.name
            ):
                raise TypeError(
                    'INTERNAL ERROR: forwarded array result changed destination'
                )
            return [*destination_prelude, *prelude]
        statements: list[hir.AST] = []
        if isinstance(item, hir.ArrayLiteral):
            if len(item.items) != array_type.length:
                raise TypeError('INTERNAL ERROR: checked array result length changed')
            for index, element in enumerate(item.items):
                target_address = self._array_element_address(
                    dest,
                    index,
                    array_type.element,
                    element.loc,
                )
                if isinstance(array_type.element, ty.ArrayType):
                    nested_dest = self._array_load(
                        target_address,
                        array_type.element,
                        element.loc,
                    )
                    statements.extend(
                        self._write_array_result_value(
                            nested_dest,
                            element,
                            array_type.element,
                        )
                    )
                elif isinstance(array_type.element, ty.ObjectType):
                    nested_dest = self._array_load(
                        target_address,
                        array_type.element,
                        element.loc,
                    )
                    statements.extend(
                        self._write_object_result_value(
                            nested_dest,
                            element,
                            array_type.element,
                        )
                    )
                else:
                    prelude, value = self._array_storage_value(
                        element,
                        array_type.element,
                    )
                    statements.extend(prelude)
                    statements.append(
                        self._array_store(
                            value,
                            target_address,
                            array_type.element,
                            element.loc,
                        )
                    )
        else:
            statements.extend(
                self._copy_array_into_result_storage(
                    dest,
                    item,
                    array_type,
                    item.loc,
                )
            )
        return statements

    def _copy_array_into_result_storage(
        self,
        dest: hir.AST,
        source_node: hir.AST,
        array_type: ty.ArrayType,
        loc: Span,
        *,
        source_is_pointer: bool = False,
    ) -> list[hir.AST]:
        """Recursively copy an array into already-prepared mutable storage."""

        if array_type.length is None:
            # a handle slot: fill it with an arena-backed copy that outlives the callee
            source: hir.AST = (
                replace(source_node, type='int64')
                if source_is_pointer and isinstance(source_node, hir.ExpressedIdentifier)
                else source_node
            )
            prelude, copied = self._clone_dynamic_array_value(source, array_type, arena=True)
            return [*prelude, *self._value_store(copied, dest, array_type, loc)]
        if source_is_pointer:
            raw_representation = None
            prelude, source = [], replace(source_node, type='int64')
        else:
            raw_representation = self._array_use_representation(source_node)
            prelude, source = self._extract_expression(source_node)
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            source_node,
        )
        statements = [*prelude]
        for index in range(array_type.length):
            source_address = (
                self._pointer_element_address(
                    source,
                    index,
                    element_bytes,
                    loc,
                )
                if raw_representation is not None
                else self._array_element_address(
                    source,
                    index,
                    array_type.element,
                    loc,
                )
            )
            target_address = self._array_element_address(
                dest,
                index,
                array_type.element,
                loc,
            )
            source_value = self._array_load(
                source_address,
                array_type.element,
                loc,
            )
            if isinstance(array_type.element, ty.ArrayType):
                target_value = self._array_load(
                    target_address,
                    array_type.element,
                    loc,
                )
                statements.extend(
                    self._copy_array_into_result_storage(
                        target_value,
                        source_value,
                        array_type.element,
                        loc,
                        source_is_pointer=True,
                    )
                )
            elif isinstance(array_type.element, ty.ObjectType):
                target_value = self._array_load(
                    target_address,
                    array_type.element,
                    loc,
                )
                statements.extend(
                    self._copy_object_into_result_storage(
                        target_value,
                        source_value,
                        array_type.element,
                        loc,
                    )
                )
            else:
                statements.append(
                    self._array_store(
                        source_value,
                        target_address,
                        array_type.element,
                        loc,
                    )
                )
        return statements

    def _lower_array_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
        iterator: hir.IteratorExpression,
    ) -> list[hir.AST]:
        """Lower left-to-right reads from an array without choosing alias semantics."""

        array_type = iterator.iterable.type
        if not isinstance(array_type, ty.ArrayType):
            raise TypeError('INTERNAL ERROR: array iterator has no array type')
        raw_representation = self._array_use_representation(iterator.iterable)
        prelude, array = self._extract_expression(iterator.iterable)
        offset = self._new_iterator_temp(iterator)
        offset_value = replace(offset, loc=iterator.loc)
        runtime_target_type = self._lower_runtime_value_type(array_type.element)
        target = replace(
            iterator.target,
            loc=iterator.loc,
            type=runtime_target_type,
        )
        element_bytes, _signed = self._array_element_layout(
            array_type.element,
            iterator,
        )
        address = (
            self._pointer_element_address(
                array,
                offset_value,
                element_bytes,
                iterator.loc,
            )
            if raw_representation is not None
            else self._array_element_address(
                array,
                offset_value,
                array_type.element,
                iterator.loc,
            )
        )
        value = self._array_load(address, array_type.element, iterator.loc)
        updates = [
            hir.Assign(
                iterator.loc,
                ty.VOID_TYPE,
                target,
                '=',
                value,
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
        length = (
            self._int64_literal(iterator.loc, iterator.count)
            if iterator.count is not None
            else self._load_i64_field(array, ARRAY_LENGTH_OFFSET, iterator.loc)
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
                    hir.Block(
                        arm.body.loc,
                        ty.VOID_TYPE,
                        [*updates, *body_items],
                        True,
                    ),
                )
            ],
            None,
        )
        placeholder = (
            self._int64_literal(iterator.loc, 0)
            if runtime_target_type == 'int64'
            and not isinstance(array_type.element, ty.IntegerLiteralType)
            else self._default_placeholder(array_type.element, iterator.loc)
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
                runtime_target_type,
                placeholder,
                binding_id=iterator.target.binding_id,
            ),
            loop,
        ]

