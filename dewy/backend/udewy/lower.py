"""Prepare checked HIR for udewy's callable and structured-flow model.

This module sits between semantic checking and source emission. It is not the
general HIR-to-MIR pass: it handles callable constructs that are valid Dewy HIR
but cannot be represented directly by udewy:

- udewy functions must be top-level, so non-capturing local functions are
  collected, assigned module-level symbols, and hoisted;
- udewy has no runtime overload sets, so statically selected overload calls are
  rewritten to their concrete function alternatives;
- udewy has no closures, so references to enclosing function values are
  diagnosed before emission;
- udewy control flow is statement-only, so scalar control-flow expressions
  are extracted into typed temporaries and branch assignments;
- labeled exits are translated into integer signals propagated through nested
  structured loops;
- fresh local arrays become stack allocations with width-specific stores, while
  module arrays receive static backing and indexed operations become memory
  intrinsics;
- finite static range iterators become counted loops with scaled offsets,
  while semantically unbounded integer iterators remain blocked on bigint
  target support.

Lowering has two phases. Discovery replays lexical scope resolution, records
function units and captures, and preserves the type checker's forward-function
binding behavior. Transformation then removes compile-time function/overload
declarations and rewrites callable references to allocated symbols. Keeping
this work separate from ``emit`` makes the lowering rules
independently testable and leaves the checked HIR unchanged for diagnostics and
display.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Literal, NoReturn

from ...parser import t0
from ...reporting import Error, Pointer, Span, SrcFile
from ...semantic import builtins, hir, ty
from ...semantic.errors import NotImplementedYet
from ...semantic.hir_display import type_to_dewy
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


ARRAY_DATA_OFFSET = 0
ARRAY_LENGTH_OFFSET = 8
ARRAY_CAPACITY_OFFSET = 16
ARRAY_STRIDE_OFFSET = 24
ARRAY_FLAGS_OFFSET = 32
ARRAY_OWNER_OFFSET = 40
ARRAY_DESCRIPTOR_SIZE = 48
ARRAY_MUTABLE = 1
ARRAY_BORROWED_STATIC = 2

type ArrayRepresentation = Literal[
    'descriptor',
    'stack_data',
    'static_words',
    'static_bytes',
]
type ArrayUse = Literal[
    'length',
    'index_read',
    'index_write',
    'alias',
    'call_boundary',
    'call_boundary_pending',
    'safe_call_boundary',
    'representation',
]

STRING_DATA_OFFSET = 0
STRING_BYTE_LENGTH_OFFSET = 8
STRING_BOUNDARIES_OFFSET = 16
STRING_GRAPHEME_LENGTH_OFFSET = 24
STRING_START_OFFSET = 32
STRING_DESCRIPTOR_SIZE = 40


@dataclass
class LoweredFunction:
    """One concrete function that the udewy backend must emit at module scope."""

    symbol: str
    literal: hir.FunctionLiteral


@dataclass
class LoweredProgram:
    """Result of callable legalization.

    ``functions`` contains every original top-level function plus hoisted local
    and inline alternatives. ``globals`` contains module storage declarations,
    while ``startup_items`` initializes that storage and executes other
    top-level code in source order.
    """

    functions: list[LoweredFunction]
    globals: list[hir.Declare]
    startup_items: list[hir.AST]
    user_main_symbol: str | None
    startup_symbol: str
    needs_startup: bool


@dataclass
class _Scope:
    """A reconstructed lexical scope used to resolve mutable, unbound HIR names.

    HIR identifiers currently retain only their source spelling and type, not a
    definition ID. The lowering pass therefore mirrors semantic scope rules and
    records the binding selected for each identifier occurrence.

    ``display_path`` is a readable lexical path used only when symbol
    disambiguation requires scope qualification. The first function-body block
    is transparent in that path; nested anonymous blocks use ``scope_N``.
    """

    parent: _Scope | None
    display_path: tuple[str, ...]
    owner_function: _FunctionDef | None
    bindings: dict[str, _Binding]
    next_block_ordinal: int = 1

    def resolve(self, name: str) -> _Binding | None:
        """Return the nearest lexical binding for ``name``."""
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.bindings:
                return scope.bindings[name]
            scope = scope.parent
        return None


@dataclass
class _Binding:
    """A declaration reconstructed from HIR.

    ``kind`` distinguishes parameters and ordinary values from function and
    compile-time overload bindings. ``owner_function`` identifies values that
    would need closure capture when referenced by another function.
    """

    order: int
    name: str
    kind: str
    owner_function: _FunctionDef | None
    expr: hir.AST | None
    semantic_id: int | None
    function: _FunctionDef | None = None
    emitted_name: str | None = None


@dataclass
class _FunctionDef:
    """Internal identity for a concrete function before its symbol is chosen.

    ``logical_name`` is the source binding name, or ``anon`` for a bare
    function expression. Inline overload alternatives share their overload
    binding's logical name and set ``overload_member`` so their signatures
    participate in mangling.
    """

    order: int
    logical_name: str
    literal: hir.FunctionLiteral
    definition_scope: _Scope
    overload_member: bool
    symbol: str = ''
    optional_result_name: str | None = None


@dataclass(frozen=True)
class ArrayParameterAnalysis:
    function: _FunctionDef
    parameter: hir.Param
    alias_group: frozenset[int]
    uses: frozenset[ArrayUse]
    adapter_safe: bool


@dataclass(frozen=True)
class ArrayCallBoundaryAnalysis:
    function: _FunctionDef | None
    argument: hir.AST
    position: int | str
    parameter: hir.Param | None
    source_binding_id: int | None
    source_alias_group: frozenset[int]
    safe: bool


class _Lowerer:
    """Discover callable units, validate captures, and rewrite them for udewy."""

    def __init__(self, root: hir.Block, srcfile: SrcFile):
        """Initialize per-program identity maps and deterministic counters."""
        self.root = root
        self.srcfile = srcfile
        self.module_scope = _Scope(None, (), None, {})
        self.next_binding_order = 0
        self.next_function_order = 0
        self.functions: list[_FunctionDef] = []
        self.function_by_literal: dict[int, _FunctionDef] = {}
        self.declare_bindings: dict[int, _Binding] = {}
        self.binding_by_semantic_id: dict[int, _Binding] = {}
        self.identifier_bindings: dict[int, _Binding | None] = {}
        self.captures: dict[int, list[tuple[hir.ExpressedIdentifier, _Binding]]] = defaultdict(list)
        self.source_names: set[str] = set()
        self.next_flow_temp = 1
        self.next_eager_temp = 1
        self.next_array_temp = 1
        self.next_string_temp = 1
        self.next_object_temp = 1
        self.next_iterator_temp = 1
        self.next_iterator_value = 1
        self.next_optional_temp = 1
        self.next_default_temp = 1
        self.next_loop_signal = 1
        self.loop_signal_levels: hir.ExpressedIdentifier | None = None
        self.loop_signal_kind: hir.ExpressedIdentifier | None = None
        self.lower_loop_depth = 0
        self.lowering_module_startup = False
        self.optional_payloads: dict[int, ty.TypeExpr] = {}
        self.optional_globals_initialized: set[int] = set()
        self.object_globals_initialized: set[int] = set()
        self.call_optional_args: dict[int, list[ty.TypeExpr | None]] = {}
        self.call_optional_kwargs: dict[int, dict[str, ty.TypeExpr]] = {}
        self.array_representations: dict[int, ArrayRepresentation] = {}
        self.array_declarations: dict[int, hir.Declare] = {}
        self.array_uses: dict[int, set[ArrayUse]] = defaultdict(set)
        self.array_alias_edges: dict[int, int] = {}
        self.array_alias_groups: dict[int, frozenset[int]] = {}
        self.array_alias_group_by_binding: dict[int, int] = {}
        self.array_group_uses: dict[int, frozenset[ArrayUse]] = {}
        self.array_parameters: dict[int, tuple[_FunctionDef, hir.Param]] = {}
        self.array_parameter_analyses: dict[int, ArrayParameterAnalysis] = {}
        self.array_calls: list[hir.FunctionCall] = []
        self.array_call_boundary_analyses: dict[
            tuple[int, int | str],
            ArrayCallBoundaryAnalysis,
        ] = {}
        self.current_optional_result: hir.ExpressedIdentifier | None = None
        self.current_object_result: hir.ExpressedIdentifier | None = None
        self.current_object_receiver: hir.ExpressedIdentifier | None = None
        self.current_object_type: ty.ObjectType | None = None
        self.current_object_field_ids: set[int] = set()
        self.current_object_field_names: dict[int, str] = {}
        self.object_literal_contexts: list[
            tuple[hir.AST, ty.ObjectType, dict[int, str]]
        ] = []
        self.needs_startup = False
        self.startup_symbol = '__dewy_top_level'
        self.user_main_base = '__dewy_user_main'

    def lower(self) -> LoweredProgram:
        """Run discovery, validation, symbol allocation, and HIR rewriting."""
        self._discover_block(
            self.root,
            self.module_scope,
            current_function=None,
            create_scope=False,
            function_body=False,
        )
        self._classify_array_representations()
        self._check_captures()
        self.needs_startup = any(
            not (
                isinstance(item, hir.Declare)
                and (
                    (
                        (binding := self.declare_bindings.get(id(item))) is not None
                        and binding.kind in {'function', 'overload'}
                    )
                    or isinstance(item.expr, hir.TypeValue)
                    or self._array_representation(item) in {
                        'static_words',
                        'static_bytes',
                    }
                )
            )
            and not isinstance(item, hir.ScopeMetatag)
            for item in self.root.items
        )
        if self.needs_startup:
            self.startup_symbol = self._internal_symbol('__dewy_top_level')
            self.user_main_base = self._internal_symbol('__dewy_user_main')
        self._allocate_symbols()

        lowered_functions = [
            self._lower_function(function)
            for function in sorted(self.functions, key=lambda item: item.order)
        ]

        globals_: list[hir.Declare] = []
        startup_sources: list[hir.AST] = []
        for item in self.root.items:
            binding = self.declare_bindings.get(id(item))
            if binding is not None and binding.kind in {'function', 'overload'}:
                continue
            transformed = self._transform_node(item)
            if transformed is None:
                continue
            if isinstance(transformed, hir.Declare):
                representation = self._array_representation(transformed)
                if representation == 'static_words' or representation == 'static_bytes':
                    globals_.append(
                        self._static_array_global(transformed, representation)
                    )
                    continue
                globals_.append(self._global_storage(transformed))
                assignment = hir.Assign(
                    transformed.loc,
                    ty.VOID_TYPE,
                    hir.ExpressedIdentifier(
                        transformed.loc,
                        transformed.expr.type,
                        transformed.name,
                        binding_id=transformed.binding_id,
                    ),
                    '=',
                    transformed.expr,
                )
                startup_sources.append(assignment)
            else:
                startup_sources.append(transformed)
        startup_items: list[hir.AST] = []
        if startup_sources:
            self.lowering_module_startup = True
            startup = self._lower_function_body(
                hir.Block(
                    self.root.loc,
                    ty.VOID_TYPE,
                    startup_sources,
                    True,
                ),
                ty.VOID_TYPE,
            )
            self.lowering_module_startup = False
            if not isinstance(startup, hir.Block):
                raise TypeError('INTERNAL ERROR: top-level startup did not lower to a block')
            startup_items = startup.items
        main = self.module_scope.bindings.get('main')
        user_main_symbol = (
            main.function.symbol
            if main is not None and main.function is not None
            else None
        )
        return LoweredProgram(
            lowered_functions,
            globals_,
            startup_items,
            user_main_symbol,
            self.startup_symbol,
            self.needs_startup,
        )

    def _lower_function(self, function: _FunctionDef) -> LoweredFunction:
        literal = function.literal
        if literal.rest_args is not None:
            self._target_error(literal, 'rest parameters and argument spreading')
        result_payload = ty.optional_payload(literal.rettype)
        object_result = isinstance(literal.rettype, ty.ObjectType)
        if isinstance(result_payload, ty.ArrayType):
            self._target_error(
                literal,
                'optional array returns require array ownership lowering',
            )
        rettype = (
            ty.VOID_TYPE
            if result_payload is not None or object_result
            else self._target_scalar_type(literal.rettype, literal)
        )
        lowered_pos: list[hir.Param | hir.BoundParam] = []
        default_prologue: list[hir.AST] = []
        parameter_prologue: list[hir.AST] = []

        def lower_param(param: hir.Param) -> hir.Param:
            if (
                isinstance(param.type, ty.TypeOr)
                and 'undefined' in param.type.items
                and ty.optional_payload(param.type) is None
            ):
                self._target_error(literal, 'heterogeneous optional parameter type')
            if isinstance(param.type, ty.ObjectType):
                incoming_name = self._new_object_name(f'arg_{param.name}')
                incoming = hir.ExpressedIdentifier(
                    literal.loc,
                    'int64',
                    incoming_name,
                )
                cell = hir.ExpressedIdentifier(
                    literal.loc,
                    'int64',
                    param.name,
                    binding_id=param.binding_id,
                )
                size, _offsets = self._object_layout(param.type, literal)
                parameter_prologue.append(
                    hir.Declare(
                        literal.loc,
                        ty.VOID_TYPE,
                        'let',
                        param.name,
                        'int64',
                        self._object_allocation(literal.loc, size),
                        binding_id=param.binding_id,
                    )
                )
                parameter_prologue.extend(
                    self._object_copy(cell, incoming, param.type, literal.loc)
                )
                return replace(
                    param,
                    name=incoming_name,
                    type='int64',
                    binding_id=None,
                )
            payload = ty.optional_payload(param.type)
            if payload is None:
                return self._transform_param(param)
            incoming_name = self._new_optional_name(f'arg_{param.name}')
            incoming = hir.ExpressedIdentifier(
                literal.loc,
                param.type,
                incoming_name,
            )
            cell = hir.ExpressedIdentifier(
                literal.loc,
                'int64',
                param.name,
                binding_id=param.binding_id,
            )
            parameter_prologue.append(
                hir.Declare(
                    literal.loc,
                    ty.VOID_TYPE,
                    'let',
                    param.name,
                    'int64',
                    self._optional_allocation(literal.loc),
                    binding_id=param.binding_id,
                )
            )
            parameter_prologue.extend(self._optional_write(cell, incoming, payload))
            return replace(
                param,
                name=incoming_name,
                type='int64',
                binding_id=None,
            )

        lowered_pos = [lower_param(param) for param in literal.pos_or_kw_args]
        for param in literal.kw_only_args:
            if not isinstance(param, hir.BoundParam):
                lowered_pos.append(lower_param(param))
                continue
            if isinstance(param.type, ty.ObjectType):
                self._target_error(literal, 'object parameter defaults')
            if ty.optional_payload(param.type) is not None:
                self._target_error(literal, 'optional parameter defaults')
            incoming_name = self._new_default_name(f'arg_{param.name}')
            present_name = self._new_default_name(f'has_{param.name}')
            lowered_pos.extend([
                hir.Param(
                    incoming_name,
                    self._lower_runtime_value_type(param.type),
                ),
                hir.Param(present_name, 'bool'),
            ])
            incoming = hir.ExpressedIdentifier(
                literal.loc,
                param.type,
                incoming_name,
            )
            target = hir.ExpressedIdentifier(
                literal.loc,
                param.type,
                param.name,
                binding_id=param.binding_id,
            )
            default = self._require_node(self._transform_node(param.value))
            default_prologue.extend([
                hir.Declare(
                    literal.loc,
                    ty.VOID_TYPE,
                    'let',
                    param.name,
                    param.type,
                    incoming,
                    binding_id=param.binding_id,
                ),
                hir.Flow(
                    literal.loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            literal.loc,
                            ty.BOTTOM_TYPE,
                            self._bool_not(hir.ExpressedIdentifier(
                                literal.loc,
                                'bool',
                                present_name,
                            )),
                            hir.Assign(
                                literal.loc,
                                ty.VOID_TYPE,
                                target,
                                '=',
                                default,
                            ),
                        ),
                    ],
                    None,
                ),
            ])
        receiver = None
        if literal.object_receiver:
            receiver_name = self._new_object_name('self')
            receiver = hir.ExpressedIdentifier(literal.loc, 'int64', receiver_name)
            lowered_pos = [hir.Param(receiver_name, 'int64'), *lowered_pos]
        result_target = None
        object_result_target = None
        if result_payload is not None or object_result:
            assert function.optional_result_name is not None
            lowered_pos.append(
                hir.Param(function.optional_result_name, 'int64')
            )
            target = hir.ExpressedIdentifier(
                literal.loc,
                literal.rettype,
                function.optional_result_name,
            )
            if object_result:
                object_result_target = target
            else:
                result_target = target
        previous_result = self.current_optional_result
        previous_object_result = self.current_object_result
        previous_receiver = self.current_object_receiver
        previous_object_type = self.current_object_type
        previous_field_ids = self.current_object_field_ids
        previous_field_names = self.current_object_field_names
        self.current_optional_result = result_target
        self.current_object_result = object_result_target
        self.current_object_receiver = receiver
        self.current_object_type = literal.object_type
        self.current_object_field_ids = {binding_id for binding_id, _name in literal.object_fields}
        self.current_object_field_names = {
            binding_id: name for binding_id, name in literal.object_fields
        }
        transformed_body = self._require_node(self._transform_node(literal.body))
        if default_prologue:
            if isinstance(transformed_body, hir.Block):
                transformed_body = replace(
                    transformed_body,
                    items=[*default_prologue, *transformed_body.items],
                )
            else:
                transformed_body = hir.Block(
                    transformed_body.loc,
                    transformed_body.type,
                    [*default_prologue, transformed_body],
                    True,
                )
        body = self._lower_function_body(transformed_body, literal.rettype)
        self.current_optional_result = previous_result
        self.current_object_result = previous_object_result
        self.current_object_receiver = previous_receiver
        self.current_object_type = previous_object_type
        self.current_object_field_ids = previous_field_ids
        self.current_object_field_names = previous_field_names
        if parameter_prologue:
            if isinstance(body, hir.Block):
                body = replace(body, items=[*parameter_prologue, *body.items])
            else:
                body = hir.Block(body.loc, body.type, [*parameter_prologue, body], True)
        function_type = self._lower_callable_type(literal.type)
        if literal.object_receiver and isinstance(function_type, ty.FunctionType):
            function_type = replace(
                function_type,
                pos_or_kw=[ty.PosOrKwArg(None, 'int64'), *function_type.pos_or_kw],
            )
        return LoweredFunction(
            function.symbol,
            replace(
                literal,
                type=function_type,
                pos_or_kw_args=lowered_pos,
                kw_only_args=[],
                rest_args=None,
                rettype=rettype,
                body=body,
            ),
        )

    def _lower_callable_type(self, type_: ty.Type) -> ty.Type:
        if not isinstance(type_, ty.FunctionType):
            return type_
        pos = [
            ty.PosOrKwArg(
                param.name,
                self._lower_runtime_value_type(param.type),
            )
            for param in type_.pos_or_kw
        ]
        for param in type_.kw_only:
            pos.append(ty.PosOrKwArg(
                param.name,
                self._lower_runtime_value_type(param.type),
            ))
            if not param.required:
                pos.append(ty.PosOrKwArg(None, 'bool'))
        rettype: ty.TypeExpr = self._lower_runtime_value_type(type_.ret)
        if isinstance(type_.ret, ty.ObjectType) or ty.optional_payload(type_.ret) is not None:
            pos.append(ty.PosOrKwArg(None, 'int64'))
            rettype = ty.VOID_TYPE
        return replace(
            type_,
            pos_or_kw=pos,
            kw_only=[],
            rest=None,
            ret=rettype,
        )

    def _lower_runtime_value_type(self, type_: ty.TypeExpr) -> ty.TypeExpr:
        if ty.optional_payload(type_) is not None:
            return 'int64'
        if isinstance(type_, ty.QuantityType):
            return self._lower_runtime_value_type(type_.number)
        if isinstance(type_, ty.IntegerLiteralType):
            return 'int64'
        if isinstance(
            type_,
            (
                ty.ArrayType,
                ty.ObjectType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(type_, str)
            and type_ in {'string', 'grapheme', 'char'}
        ):
            return 'int64'
        if isinstance(type_, ty.FunctionType):
            lowered = self._lower_callable_type(type_)
            assert isinstance(lowered, ty.FunctionType)
            return lowered
        return type_

    def _target_scalar_type(self, type_: ty.Type, node: hir.AST) -> ty.Type:
        if (
            isinstance(type_, ty.TypeOr)
            and 'undefined' in type_.items
            and ty.optional_payload(type_) is None
        ):
            self._target_error(
                node,
                'heterogeneous runtime union containing `undefined`',
            )
        if isinstance(type_, ty.ArrayType):
            self._target_error(node, 'array return values are not supported by udewy')
        if isinstance(type_, ty.QuantityType):
            return self._target_scalar_type(type_.number, node)
        if isinstance(type_, ty.StringLiteralType):
            return 'int64'
        if isinstance(type_, ty.BinaryLiteralType):
            return 'int64'
        if isinstance(type_, ty.StringType) or (
            isinstance(type_, str)
            and type_ in {'string', 'grapheme', 'char'}
        ):
            return 'int64'
        if not isinstance(type_, ty.IntegerLiteralType):
            return type_
        if ty.integer_literal_fits(type_.value, 'int64'):
            return 'int64'
        raise NotImplementedYet(Error(
            srcfile=self.srcfile,
            title='udewy scalar representation requires bigint lowering',
            pointer_messages=[
                Pointer(
                    span=node.loc,
                    message=f'`{type_.value}` does not fit in `int64`',
                )
            ],
        ))

    def _internal_symbol(self, base: str) -> str:
        """Choose a generated module symbol outside the source namespace."""
        if base not in self.source_names:
            return base
        ordinal = 2
        while f'{base}_{ordinal}' in self.source_names:
            ordinal += 1
        return f'{base}_{ordinal}'

    def _global_storage(self, declaration: hir.Declare) -> hir.Declare:
        """Create inert udewy storage initialized later by module startup."""
        annotation = declaration.annotation or declaration.expr.type
        if (
            isinstance(annotation, ty.TypeOr)
            and 'undefined' in annotation.items
            and ty.optional_payload(annotation) is None
        ):
            self._target_error(
                declaration,
                'heterogeneous runtime union containing `undefined`',
            )
        if isinstance(annotation, ty.IntegerLiteralType):
            if not ty.integer_literal_fits(annotation.value, 'int64'):
                raise NotImplementedYet(Error(
                    srcfile=self.srcfile,
                    title='udewy top-level storage requires bigint lowering',
                    pointer_messages=[
                        Pointer(
                            span=declaration.loc,
                            message=f'`{declaration.name}` does not fit in `int64`',
                        )
                    ],
                ))
            annotation = 'int64'
        if isinstance(
            annotation,
            (
                ty.ArrayType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(annotation, str)
            and annotation in {'string', 'grapheme', 'char'}
        ):
            annotation = 'int64'
        if isinstance(annotation, ty.QuantityType):
            annotation = self._lower_runtime_value_type(annotation)
        if isinstance(annotation, ty.ObjectType):
            annotation = 'int64'
        if ty.optional_payload(annotation) is not None:
            annotation = 'int64'
        if annotation == 'bool':
            initializer: hir.AST = hir.Bool(declaration.loc, 'bool', False)
        elif (
            isinstance(annotation, str)
            and annotation in {
                'int',
                'uint',
                'uint8',
                'uint16',
                'uint32',
                'uint64',
                'int8',
                'int16',
                'int32',
                'int64',
            }
        ):
            initializer = hir.Integer(
                declaration.loc,
                annotation,
                '',
                0,
            )
        else:
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy top-level storage is not implemented for this type',
                pointer_messages=[
                    Pointer(
                        span=declaration.loc,
                        message=(
                            f'`{declaration.name}` has type '
                            f'`{type_to_dewy(annotation)}`'
                        ),
                    )
                ],
            ))
        return replace(
            declaration,
            decltype='let',
            annotation=annotation,
            expr=initializer,
        )

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

    def _new_binding(
        self,
        scope: _Scope,
        name: str,
        kind: str,
        owner_function: _FunctionDef | None,
        expr: hir.AST | None,
        semantic_id: int | None = None,
    ) -> _Binding:
        """Register a deterministic binding in the current lexical scope."""
        binding = _Binding(
            self.next_binding_order,
            name,
            kind,
            owner_function,
            expr,
            semantic_id,
        )
        self.next_binding_order += 1
        scope.bindings[name] = binding
        if semantic_id is not None:
            self.binding_by_semantic_id[semantic_id] = binding
        self.source_names.add(name)
        return binding

    def _new_block_scope(
        self,
        parent: _Scope,
        current_function: _FunctionDef | None,
        *,
        function_body: bool,
    ) -> _Scope:
        """Create a child block scope and its human-readable symbol path."""
        ordinal = parent.next_block_ordinal
        parent.next_block_ordinal += 1
        display_path = (
            parent.display_path
            if function_body
            else (*parent.display_path, f'scope_{ordinal}')
        )
        return _Scope(parent, display_path, current_function, {})

    def _discover_block(
        self,
        block: hir.Block,
        scope: _Scope,
        *,
        current_function: _FunctionDef | None,
        create_scope: bool = True,
        function_body: bool = False,
    ) -> None:
        """Discover a block using the type checker's two-pass function binding.

        Checked declarations are pre-bound before any item is visited. Binding
        IDs preserve semantic resolution even for deferred function bodies.
        """
        if block.scoped and create_scope:
            scope = self._new_block_scope(
                scope,
                current_function,
                function_body=function_body,
            )
        for item in block.items:
            if isinstance(item, hir.Declare):
                kind = (
                    'function'
                    if isinstance(item.expr, hir.FunctionLiteral)
                    else 'overload'
                    if isinstance(item.expr.type, ty.OverloadType)
                    else 'value'
                )
                binding = self._new_binding(
                    scope,
                    item.name,
                    kind,
                    current_function,
                    item.expr,
                    item.binding_id,
                )
                self.declare_bindings[id(item)] = binding
                if (
                    item.binding_id is not None
                    and isinstance(item.annotation or item.expr.type, ty.ArrayType)
                ):
                    self.array_representations[item.binding_id] = 'descriptor'
                    self.array_declarations[item.binding_id] = item
                payload = ty.optional_payload(item.annotation or item.expr.type)
                if payload is not None and item.binding_id is not None:
                    self.optional_payloads[item.binding_id] = payload

        for item in block.items:
            if isinstance(item, hir.Declare):
                self._discover_declare(item, scope, current_function)
            else:
                self._discover_node(item, scope, current_function)

    def _discover_declare(
        self,
        declare: hir.Declare,
        scope: _Scope,
        current_function: _FunctionDef | None,
    ) -> None:
        """Classify and register one declaration.

        Function declarations were pre-bound by ``_discover_block``. Overload
        declarations are compile-time callable sets; all other declarations
        are runtime values.
        """
        binding = self.declare_bindings.get(id(declare))
        if binding is not None:
            if isinstance(declare.expr, hir.FunctionLiteral):
                function = self._new_function(
                    declare.expr,
                    declare.name,
                    scope,
                    overload_member=False,
                )
                binding.function = function
            else:
                array_use: ArrayUse = (
                    'alias'
                    if self._record_local_array_alias(
                        declare,
                        binding,
                        scope,
                        current_function,
                    )
                    else 'representation'
                )
                self._discover_node(
                    declare.expr,
                    scope,
                    current_function,
                    suggested_name=declare.name if binding.kind == 'overload' else None,
                    overload_member=binding.kind == 'overload',
                    array_use=array_use,
                )
            return

        overload = isinstance(declare.expr.type, ty.OverloadType)
        self._discover_node(
            declare.expr,
            scope,
            current_function,
            suggested_name=declare.name if overload else None,
            overload_member=overload,
        )
        kind = 'overload' if overload else 'value'
        binding = self._new_binding(
            scope,
            declare.name,
            kind,
            current_function,
            declare.expr,
            declare.binding_id,
        )
        self.declare_bindings[id(declare)] = binding
        if (
            declare.binding_id is not None
            and isinstance(declare.annotation or declare.expr.type, ty.ArrayType)
        ):
            self.array_representations[declare.binding_id] = 'descriptor'
            self.array_declarations[declare.binding_id] = declare

    def _record_local_array_alias(
        self,
        declaration: hir.Declare,
        binding: _Binding,
        scope: _Scope,
        current_function: _FunctionDef | None,
    ) -> bool:
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

    def _new_function(
        self,
        literal: hir.FunctionLiteral,
        logical_name: str,
        definition_scope: _Scope,
        *,
        overload_member: bool,
    ) -> _FunctionDef:
        """Create a concrete function unit and discover its lexical body."""
        existing = self.function_by_literal.get(id(literal))
        if existing is not None:
            return existing
        function = _FunctionDef(
            self.next_function_order,
            logical_name,
            literal,
            definition_scope,
            overload_member,
        )
        if ty.optional_payload(literal.rettype) is not None or isinstance(
            literal.rettype,
            ty.ObjectType,
        ):
            function.optional_result_name = self._new_optional_name('result')
        self.next_function_order += 1
        self.functions.append(function)
        self.function_by_literal[id(literal)] = function

        for param in [
            *literal.pos_or_kw_args,
            *literal.kw_only_args,
            *([literal.rest_args] if literal.rest_args is not None else []),
        ]:
            if isinstance(param, hir.BoundParam):
                self._discover_node(
                    param.value,
                    definition_scope,
                    definition_scope.owner_function,
                )

        function_scope = _Scope(
            definition_scope,
            (*definition_scope.display_path, logical_name),
            function,
            {},
        )
        for param in literal.pos_or_kw_args:
            self._new_binding(
                function_scope,
                param.name,
                'param',
                function,
                None,
                param.binding_id,
            )
            if isinstance(param.type, ty.ArrayType) and param.binding_id is not None:
                self.array_parameters[param.binding_id] = (function, param)
            payload = ty.optional_payload(param.type)
            if payload is not None and param.binding_id is not None:
                self.optional_payloads[param.binding_id] = payload
        for param in literal.kw_only_args:
            self._new_binding(
                function_scope,
                param.name,
                'param',
                function,
                None,
                param.binding_id,
            )
            if isinstance(param.type, ty.ArrayType) and param.binding_id is not None:
                self.array_parameters[param.binding_id] = (function, param)
            payload = ty.optional_payload(param.type)
            if payload is not None and param.binding_id is not None:
                self.optional_payloads[param.binding_id] = payload
        if literal.rest_args is not None:
            self._new_binding(
                function_scope,
                literal.rest_args.name,
                'param',
                function,
                None,
                literal.rest_args.binding_id,
            )
            if (
                isinstance(literal.rest_args.type, ty.ArrayType)
                and literal.rest_args.binding_id is not None
            ):
                self.array_parameters[literal.rest_args.binding_id] = (
                    function,
                    literal.rest_args,
                )
            payload = ty.optional_payload(literal.rest_args.type)
            if payload is not None and literal.rest_args.binding_id is not None:
                self.optional_payloads[literal.rest_args.binding_id] = payload
        if isinstance(literal.body, hir.Block):
            self._discover_block(
                literal.body,
                function_scope,
                current_function=function,
                function_body=True,
            )
        else:
            self._discover_node(literal.body, function_scope, function)
        return function

    def _discover_node(
        self,
        node: hir.AST,
        scope: _Scope,
        current_function: _FunctionDef | None,
        *,
        suggested_name: str | None = None,
        overload_member: bool = False,
        array_use: ArrayUse = 'representation',
    ) -> None:
        """Resolve names and recursively collect callable constructs in ``node``."""
        if isinstance(node, hir.ExpressedIdentifier):
            binding = (
                self.binding_by_semantic_id.get(node.binding_id)
                if node.binding_id is not None
                else scope.resolve(node.name)
            )
            self.identifier_bindings[id(node)] = binding
            if binding is not None and binding.semantic_id is not None:
                effective_use = (
                    'representation'
                    if binding.owner_function is not None
                    and binding.owner_function is not current_function
                    else array_use
                )
                self.array_uses[binding.semantic_id].add(effective_use)
            if (
                current_function is not None
                and binding is not None
                and binding.kind in {'param', 'value'}
                and binding.owner_function is not None
                and binding.owner_function is not current_function
            ):
                self.captures[id(current_function.literal)].append((node, binding))
            return
        if isinstance(node, hir.FunctionLiteral):
            self._new_function(
                node,
                suggested_name or 'anon',
                scope,
                overload_member=overload_member,
            )
            return
        if isinstance(node, hir.OverloadedFunction):
            for alternate in node.alternates:
                self._discover_node(
                    alternate,
                    scope,
                    current_function,
                    suggested_name=suggested_name,
                    overload_member=True,
                )
            return
        if isinstance(node, hir.Block):
            if not node.scoped and len(node.items) == 1:
                self._discover_node(
                    node.items[0],
                    scope,
                    current_function,
                    suggested_name=suggested_name,
                    overload_member=overload_member,
                    array_use=array_use,
                )
                return
            self._discover_block(node, scope, current_function=current_function)
            return
        if isinstance(node, hir.Declare):
            self._discover_declare(node, scope, current_function)
            return
        if isinstance(node, hir.Return):
            if node.item is not None:
                self._discover_node(node.item, scope, current_function)
            return
        if isinstance(node, hir.Flow):
            for arm in node.arms:
                iterators = (
                    [arm.condition]
                    if isinstance(arm.condition, hir.IteratorExpression)
                    else arm.condition.iterators
                    if isinstance(arm.condition, hir.MultiIteratorExpression)
                    else []
                )
                if iterators:
                    for iterator in iterators:
                        binding = self._new_binding(
                            scope,
                            iterator.target.name,
                            'value',
                            current_function,
                            None,
                            iterator.target.binding_id,
                        )
                        binding.emitted_name = self._new_iterator_name('value')
                        self.identifier_bindings[id(iterator.target)] = binding
                        payload = ty.optional_payload(iterator.target.type)
                        if payload is not None and iterator.target.binding_id is not None:
                            self.optional_payloads[iterator.target.binding_id] = payload
                        self._discover_node(
                            iterator.iterable,
                            scope,
                            current_function,
                        )
                else:
                    self._discover_node(arm.condition, scope, current_function)
                self._discover_node(arm.body, scope, current_function)
            if node.default is not None:
                self._discover_node(node.default, scope, current_function)
            return
        if isinstance(node, hir.ShortCircuit):
            self._discover_node(node.left, scope, current_function)
            self._discover_node(node.right, scope, current_function)
            return
        if isinstance(node, hir.TypeTest):
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, hir.ArrayLiteral):
            for item in node.items:
                self._discover_node(item, scope, current_function)
            return
        if isinstance(node, hir.ArrayLength):
            self._discover_node(
                node.array,
                scope,
                current_function,
                array_use='length',
            )
            return
        if isinstance(node, hir.StringLength):
            self._discover_node(node.string, scope, current_function)
            return
        if isinstance(node, hir.StringIndex):
            self._discover_node(node.string, scope, current_function)
            self._discover_node(node.index, scope, current_function)
            return
        if isinstance(node, hir.StringSlice):
            self._discover_node(node.string, scope, current_function)
            self._discover_node(node.range, scope, current_function)
            return
        if isinstance(node, hir.StringEqual):
            self._discover_node(node.left, scope, current_function)
            self._discover_node(node.right, scope, current_function)
            return
        if isinstance(node, hir.StringConcat):
            self._discover_node(node.left, scope, current_function)
            self._discover_node(node.right, scope, current_function)
            return
        if isinstance(node, hir.InterpolatedString):
            for part in node.parts:
                self._discover_node(part, scope, current_function)
            return
        if isinstance(node, hir.Index):
            self._discover_node(
                node.array,
                scope,
                current_function,
                array_use='index_read',
            )
            self._discover_node(node.index, scope, current_function)
            return
        if isinstance(node, hir.IndexAssign):
            self._discover_node(
                node.target.array,
                scope,
                current_function,
                array_use='index_write',
            )
            self._discover_node(node.target.index, scope, current_function)
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, hir.ObjectLiteral):
            for field in node.fields:
                self._discover_node(
                    field.value,
                    scope,
                    current_function,
                    suggested_name=(
                        self._new_object_name(f'method_{field.name}')
                        if isinstance(field.value, hir.FunctionLiteral)
                        else None
                    ),
                )
            return
        if isinstance(node, hir.MemberAccess):
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, hir.MemberAssign):
            self._discover_node(node.target, scope, current_function)
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, hir.TypeValue):
            return
        if isinstance(node, hir.FunctionCall):
            self._discover_node(node.func, scope, current_function)
            if any(
                isinstance(arg.type, ty.ArrayType)
                for arg in [*node.pos_args, *node.kw_args.values()]
            ):
                self.array_calls.append(node)
            for arg in node.pos_args:
                self._discover_node(
                    arg,
                    scope,
                    current_function,
                    array_use='call_boundary_pending',
                )
            for arg in node.kw_args.values():
                self._discover_node(
                    arg,
                    scope,
                    current_function,
                    array_use='call_boundary_pending',
                )
            return
        if isinstance(node, hir.Assign):
            self._discover_node(node.target, scope, current_function)
            self._discover_node(node.value, scope, current_function)
            target_binding = self.identifier_bindings.get(id(node.target))
            if (
                isinstance(node.value.type, (ty.ArrayType, ty.ObjectType))
                and current_function is not None
                and target_binding is not None
                and target_binding.owner_function is None
            ):
                self._target_error(
                    node,
                    'a function-local array or object cannot escape into module storage',
                )
            return
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            self._discover_node(
                node.expr,
                scope,
                current_function,
                array_use='representation',
            )
            return
        if isinstance(node, hir.TypeBlock):
            for item in node.items:
                self._discover_node(item, scope, current_function)
            return
        if isinstance(node, hir.Range):
            items = [
                *([] if node.step_pair is None else node.step_pair),
                *([] if node.left is None else [node.left]),
                *([] if node.right is None else [node.right]),
            ]
            seen: set[int] = set()
            for item in items:
                if id(item) in seen:
                    continue
                seen.add(id(item))
                self._discover_node(item, scope, current_function)

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
        allowed_uses: set[ArrayUse] = {'length', 'index_read', 'index_write'}
        for binding_id, (function, parameter) in self.array_parameters.items():
            group_id = self.array_alias_group_by_binding[binding_id]
            group = self.array_alias_groups[group_id]
            uses: frozenset[ArrayUse] = frozenset(
                use for use in self.array_group_uses[group_id] if use != 'alias'
            )
            same_function = all(
                self.binding_by_semantic_id[member].owner_function is function
                for member in group
            )
            self.array_parameter_analyses[binding_id] = ArrayParameterAnalysis(
                function,
                parameter,
                group,
                uses,
                same_function and uses <= allowed_uses,
            )

    def _analyze_array_call_boundaries(self) -> dict[int, set[ArrayUse]]:
        boundary_uses: dict[int, set[ArrayUse]] = defaultdict(set)
        self.array_call_boundary_analyses = {}
        for call in self.array_calls:
            function = self._direct_call_function(call)
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
                    and source.kind != 'param'
                    and raw_kind is not None
                    and self._raw_array_group_uses_are_safe(group, raw_kind)
                    and not (
                        raw_kind == 'static_bytes'
                        and 'index_write' in parameter_analysis.uses
                    )
                )
                if source_id is not None:
                    boundary_uses[source_id].add(
                        'safe_call_boundary' if safe else 'call_boundary'
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

    def _direct_call_function(
        self,
        call: hir.FunctionCall,
    ) -> _FunctionDef | None:
        if isinstance(call.func, hir.FunctionLiteral):
            return self.function_by_literal.get(id(call.func))
        if isinstance(call.func, hir.OverloadedFunction):
            if call.selected_method_index is None:
                return None
            functions = self._resolve_callable(call.func)
            return functions[call.selected_method_index]
        if not isinstance(call.func, hir.ExpressedIdentifier):
            return None
        binding = self.identifier_bindings.get(id(call.func))
        if binding is None:
            return None
        if binding.kind == 'function':
            return binding.function
        if binding.kind != 'overload' or call.selected_method_index is None:
            return None
        functions = self._resolve_callable(call.func)
        return functions[call.selected_method_index]

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
            if isinstance(argument.type, ty.ArrayType):
                parameter = (
                    positional_parameters[index]
                    if index < len(positional_parameters)
                    else None
                )
                arguments.append((index, argument, parameter))
        for name, argument in call.kw_args.items():
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
            if not uses <= {'length', 'index_read', 'safe_call_boundary'}:
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

    def _declaration_for_binding(self, semantic_id: int) -> hir.Declare | None:
        return next(
            (
                node
                for node in self.root.items
                if isinstance(node, hir.Declare)
                and node.binding_id == semantic_id
            ),
            None,
        )

    def _check_captures(self) -> None:
        """Reject function units that require an udewy closure environment."""
        for function in self.functions:
            captures = self.captures.get(id(function.literal), [])
            if not captures:
                continue
            use, binding = captures[0]
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy closure lowering is not implemented',
                message=(
                    f'nested function `{function.logical_name}` captures '
                    f'`{binding.name}` from an enclosing function'
                ),
                pointer_messages=[
                    Pointer(
                        span=use.loc,
                        message=f'`{binding.name}` is captured here',
                    )
                ],
            ))

    def _allocate_symbols(self) -> None:
        """Assign deterministic, readable, collision-free udewy symbols.

        Unique named functions keep their source spelling. Overload members add
        a structural signature, local collisions add a lexical scope path, and
        only remaining collisions receive source-order ordinals.
        """
        by_base: dict[str, list[_FunctionDef]] = defaultdict(list)
        for function in self.functions:
            by_base[self._symbol_base(function)].append(function)

        assigned = set(builtins.builtin_types)
        if self.needs_startup:
            assigned.update({'main', self.startup_symbol})
        for base, group in by_base.items():
            if len(group) == 1 and group[0].logical_name != 'anon':
                group[0].symbol = self._unique_symbol(base, assigned, 'local')
                continue

            top_level = next(
                (
                    function
                    for function in group
                    if function.definition_scope is self.module_scope
                    and not function.overload_member
                ),
                None,
            )
            ordered_group = (
                [top_level, *(function for function in group if function is not top_level)]
                if top_level is not None
                else group
            )
            candidates: list[tuple[_FunctionDef, str]] = []
            for function in ordered_group:
                if (
                    function is top_level
                    or function.overload_member
                    and function.definition_scope is self.module_scope
                ):
                    candidate = base
                else:
                    scope = self._scope_slug(function.definition_scope)
                    candidate = f'{base}__in_{scope}'
                candidates.append((function, candidate))

            candidate_counts: dict[str, int] = defaultdict(int)
            for function, candidate in candidates:
                candidate_counts[candidate] += 1
                ordinal = candidate_counts[candidate]
                suffix = 'overload' if function.overload_member else 'local'
                requested = candidate if ordinal == 1 else f'{candidate}__{suffix}_{ordinal}'
                function.symbol = self._unique_symbol(requested, assigned, suffix)

    def _symbol_base(self, function: _FunctionDef) -> str:
        """Return a function's preferred symbol before collision handling."""
        if self.needs_startup and function.logical_name == 'main':
            return self.user_main_base
        if function.logical_name == 'anon':
            return f'anon__{self._signature_slug(function.literal.type)}'
        if function.overload_member:
            return f'{function.logical_name}__{self._signature_slug(function.literal.type)}'
        return function.logical_name

    def _scope_slug(self, scope: _Scope) -> str:
        """Render a lexical display path as an udewy identifier component."""
        if not scope.display_path:
            return 'module'
        return '__'.join(self._slug(part) for part in scope.display_path)

    def _signature_slug(self, function_type: ty.Type) -> str:
        """Render a structural function type as a readable symbol component."""
        if not isinstance(function_type, ty.FunctionType):
            raise TypeError(f'expected FunctionType, got {function_type!r}')
        rendered = type_to_dewy(function_type)
        rendered = rendered.replace(':>', '_to_')
        rendered = rendered.replace('|', '_or_')
        rendered = rendered.replace('&', '_and_')
        rendered = rendered.replace('~', '_not_')
        return self._slug(rendered)

    @staticmethod
    def _slug(text: str) -> str:
        """Replace syntax punctuation with stable identifier separators."""
        slug = re.sub(r'[^A-Za-z0-9]+', '_', text).strip('_')
        return re.sub(r'_+', '_', slug) or 'void'

    @staticmethod
    def _unique_symbol(requested: str, assigned: set[str], suffix: str) -> str:
        """Reserve ``requested``, adding a readable ordinal if already used."""
        if requested not in assigned:
            assigned.add(requested)
            return requested
        ordinal = 2
        while f'{requested}__{suffix}_{ordinal}' in assigned:
            ordinal += 1
        symbol = f'{requested}__{suffix}_{ordinal}'
        assigned.add(symbol)
        return symbol

    def _resolve_callable(self, node: hir.AST, seen: set[int] | None = None) -> list[_FunctionDef]:
        """Flatten a callable expression into dispatch-order concrete functions.

        Identifier alternatives may themselves refer to overload bindings, so
        flattening follows those bindings recursively. The resulting order must
        match ``OverloadType.methods`` and therefore the selected method index
        recorded during type checking.
        """
        seen = set() if seen is None else seen
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            return self._resolve_callable(node.items[0], seen)
        if isinstance(node, hir.FunctionLiteral):
            return [self.function_by_literal[id(node)]]
        if isinstance(node, hir.OverloadedFunction):
            resolved: list[_FunctionDef] = []
            for alternate in node.alternates:
                resolved.extend(self._resolve_callable(alternate, seen))
            return resolved
        if isinstance(node, hir.ExpressedIdentifier):
            binding = self.identifier_bindings.get(id(node))
            if binding is None:
                self._target_error(node, f'cannot resolve callable `{node.name}` for udewy')
            if binding.order in seen:
                self._target_error(node, f'cyclic overload binding involving `{node.name}`')
            if binding.kind == 'function':
                if binding.function is None:
                    raise ValueError(f'INTERNAL ERROR: missing function for `{binding.name}`')
                return [binding.function]
            if binding.kind == 'overload' and binding.expr is not None:
                return self._resolve_callable(binding.expr, {*seen, binding.order})
        self._target_error(node, 'runtime multifunction values are not supported by udewy')

    def _transform_param(self, param: hir.Param | hir.BoundParam) -> hir.Param | hir.BoundParam:
        """Rewrite callable references inside a parameter default."""
        if isinstance(param, hir.BoundParam):
            return replace(
                param,
                type=self._lower_runtime_value_type(param.type),
                value=self._require_node(self._transform_node(param.value)),
            )
        return replace(param, type=self._lower_runtime_value_type(param.type))

    def _default_placeholder(self, type_: ty.TypeExpr, loc: Span) -> hir.AST:
        """Produce an ABI-typed value ignored when a default is selected."""

        runtime_type = self._lower_runtime_value_type(type_)
        if runtime_type == 'bool':
            return hir.Bool(loc, 'bool', False)
        if isinstance(runtime_type, ty.FunctionType):
            return hir.Transmute(
                loc,
                runtime_type,
                hir.Integer(loc, 'int64', t0.base10, 0),
            )
        if isinstance(runtime_type, ty.IntegerLiteralType):
            return hir.Integer(
                loc,
                runtime_type,
                t0.base10,
                runtime_type.value,
            )
        if isinstance(runtime_type, str) and runtime_type in {
            'int',
            'int8',
            'int16',
            'int32',
            'int64',
            'uint',
            'uint8',
            'uint16',
            'uint32',
            'uint64',
        }:
            return hir.Integer(loc, runtime_type, t0.base10, 0)
        self._target_error(
            hir.Void(loc, ty.VOID_TYPE),
            f'default parameter ABI for `{type_to_dewy(type_)}`',
        )

    def _normalize_call_arguments(
        self,
        node: hir.FunctionCall,
        function_type: ty.FunctionType,
        pos_args: list[hir.AST],
        kw_args: dict[str, hir.AST],
    ) -> tuple[
        list[hir.AST],
        list[int | str | None],
        list[ty.TypeExpr | None],
    ]:
        """Map Dewy positional/keyword arguments onto udewy positional slots."""

        remaining = dict(kw_args)
        normalized: list[hir.AST] = []
        source_positions: list[int | str | None] = []
        optional_payloads: list[ty.TypeExpr | None] = []
        for index, param in enumerate(function_type.pos_or_kw):
            if index < len(pos_args):
                argument = pos_args[index]
                source_position: int | str = index
            elif param.name is not None and param.name in remaining:
                argument = remaining.pop(param.name)
                source_position = param.name
            else:
                raise ValueError(
                    f'INTERNAL ERROR: checked call is missing required parameter `{param.name}`'
                )
            normalized.append(argument)
            source_positions.append(source_position)
            optional_payloads.append(ty.optional_payload(param.type))
        if len(pos_args) > len(function_type.pos_or_kw):
            raise ValueError('INTERNAL ERROR: rest arguments reached udewy lowering')
        for param in function_type.kw_only:
            if param.name in remaining:
                normalized.append(remaining.pop(param.name))
                source_positions.append(param.name)
                optional_payloads.append(ty.optional_payload(param.type))
                if not param.required:
                    normalized.append(hir.Bool(node.loc, 'bool', True))
                    source_positions.append(None)
                    optional_payloads.append(None)
            elif param.required:
                raise ValueError(
                    f'INTERNAL ERROR: checked call is missing keyword parameter `{param.name}`'
                )
            else:
                normalized.extend([
                    self._default_placeholder(param.type, node.loc),
                    hir.Bool(node.loc, 'bool', False),
                ])
                source_positions.extend([None, None])
                optional_payloads.extend([None, None])
        if remaining:
            names = ', '.join(sorted(remaining))
            raise ValueError(
                f'INTERNAL ERROR: checked call has unmatched keyword arguments: {names}'
            )
        return normalized, source_positions, optional_payloads

    def _transform_node(self, node: hir.AST) -> hir.AST | None:
        """Rewrite callable references and elide compile-time declarations.

        Returning ``None`` is reserved for function and overload declarations:
        their concrete units are emitted from ``LoweredProgram.functions``
        instead of at their original lexical position.
        """
        if isinstance(node, hir.ExpressedIdentifier):
            binding = self.identifier_bindings.get(id(node))
            if binding is None:
                return node
            if binding.kind == 'function':
                if binding.function is None:
                    raise ValueError(f'INTERNAL ERROR: missing function for `{binding.name}`')
                return replace(
                    node,
                    name=binding.function.symbol,
                    type=self._lower_callable_type(node.type),
                )
            if binding.kind == 'overload':
                self._target_error(node, 'runtime multifunction values are not supported by udewy')
            if binding.emitted_name is not None:
                return replace(node, name=binding.emitted_name)
            return node
        if isinstance(node, hir.FunctionLiteral):
            function = self.function_by_literal[id(node)]
            return hir.ExpressedIdentifier(
                node.loc,
                self._lower_callable_type(node.type),
                function.symbol,
            )
        if isinstance(node, hir.OverloadedFunction):
            self._target_error(node, 'runtime multifunction values are not supported by udewy')
        if isinstance(node, hir.ArrayLiteral):
            return replace(
                node,
                items=[
                    self._require_node(self._transform_node(item))
                    for item in node.items
                ],
            )
        if isinstance(node, hir.ObjectLiteral):
            return replace(
                node,
                fields=[
                    replace(
                        field,
                        value=self._require_node(self._transform_node(field.value)),
                    )
                    for field in node.fields
                ],
            )
        if isinstance(node, hir.MemberAccess):
            return replace(
                node,
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, hir.MemberAssign):
            target = self._transform_node(node.target)
            if not isinstance(target, hir.MemberAccess):
                raise TypeError('INTERNAL ERROR: member assignment target was not a member access')
            return replace(
                node,
                target=target,
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, hir.TypeValue):
            return node
        if isinstance(node, hir.ModuleNamespace):
            self._target_error(node, 'using a module namespace as a runtime value')
        if isinstance(node, hir.ArrayLength):
            return replace(
                node,
                array=self._require_node(self._transform_node(node.array)),
            )
        if isinstance(node, hir.StringLength):
            return replace(
                node,
                string=self._require_node(self._transform_node(node.string)),
            )
        if isinstance(node, hir.StringIndex):
            return replace(
                node,
                string=self._require_node(self._transform_node(node.string)),
                index=self._require_node(self._transform_node(node.index)),
            )
        if isinstance(node, hir.StringSlice):
            transformed_range = self._transform_node(node.range)
            if not isinstance(transformed_range, hir.Range):
                raise TypeError('INTERNAL ERROR: string slice range was not preserved')
            return replace(
                node,
                string=self._require_node(self._transform_node(node.string)),
                range=transformed_range,
            )
        if isinstance(node, hir.StringEqual):
            return replace(
                node,
                left=self._require_node(self._transform_node(node.left)),
                right=self._require_node(self._transform_node(node.right)),
            )
        if isinstance(node, hir.StringConcat):
            return replace(
                node,
                left=self._require_node(self._transform_node(node.left)),
                right=self._require_node(self._transform_node(node.right)),
            )
        if isinstance(node, hir.InterpolatedString):
            return replace(
                node,
                parts=[
                    self._require_node(self._transform_node(part))
                    for part in node.parts
                ],
            )
        if isinstance(node, hir.IteratorExpression):
            return replace(
                node,
                target=self._require_identifier(
                    self._transform_node(node.target)
                ),
                iterable=self._require_node(
                    self._transform_node(node.iterable)
                ),
            )
        if isinstance(node, hir.MultiIteratorExpression):
            iterators: list[hir.IteratorExpression] = []
            for iterator in node.iterators:
                transformed = self._transform_node(iterator)
                if not isinstance(transformed, hir.IteratorExpression):
                    raise TypeError('INTERNAL ERROR: multiiterator leaf was not preserved')
                iterators.append(transformed)
            return replace(node, iterators=iterators)
        if isinstance(node, hir.Index):
            return replace(
                node,
                array=self._require_node(self._transform_node(node.array)),
                index=self._require_node(self._transform_node(node.index)),
            )
        if isinstance(node, hir.IndexAssign):
            target = self._transform_node(node.target)
            if not isinstance(target, hir.Index):
                raise TypeError('INTERNAL ERROR: indexed assignment target was not an index')
            return replace(
                node,
                target=target,
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, hir.FunctionCall):
            source_function_type: ty.FunctionType | None = (
                node.func.type
                if isinstance(node.func.type, ty.FunctionType)
                else None
            )
            if isinstance(node.func.type, ty.OverloadType):
                if node.selected_method_index is None:
                    raise ValueError('INTERNAL ERROR: overload call has no selected method index')
                if (
                    isinstance(node.func, hir.ExpressedIdentifier)
                    and node.func.name in builtins.builtin_types
                ):
                    func = replace(
                        node.func,
                        type=node.func.type.methods[node.selected_method_index],
                    )
                else:
                    alternatives = self._resolve_callable(node.func)
                    if len(alternatives) != len(node.func.type.methods):
                        raise ValueError(
                            'INTERNAL ERROR: overload alternatives do not align with methods'
                        )
                    selected = alternatives[node.selected_method_index]
                    func = hir.ExpressedIdentifier(
                        node.func.loc,
                        selected.literal.type,
                        selected.symbol,
                    )
                source_function_type = node.func.type.methods[
                    node.selected_method_index
                ]
            else:
                func = self._require_node(self._transform_node(node.func))
            transformed_pos = [
                self._require_node(self._transform_node(arg))
                for arg in node.pos_args
            ]
            transformed_kw = {
                name: self._require_node(self._transform_node(arg))
                for name, arg in node.kw_args.items()
            }
            if source_function_type is not None:
                normalized, source_positions, optional_payloads = (
                    self._normalize_call_arguments(
                        node,
                        source_function_type,
                        transformed_pos,
                        transformed_kw,
                    )
                )
                func = replace(
                    func,
                    type=self._lower_callable_type(source_function_type),
                )
            else:
                normalized = transformed_pos
                source_positions = list(range(len(transformed_pos)))
                optional_payloads = [None] * len(transformed_pos)
            transformed = replace(
                node,
                func=func,
                pos_args=normalized,
                kw_args={},
                selected_method_index=None,
            )
            for index, (argument, source_position) in enumerate(zip(
                transformed.pos_args,
                source_positions,
            )):
                if source_position is None:
                    continue
                analysis = self.array_call_boundary_analyses.get(
                    (id(node), source_position)
                )
                if analysis is not None:
                    self.array_call_boundary_analyses[(id(transformed), index)] = replace(
                        analysis,
                        argument=argument,
                    )
            if source_function_type is not None:
                self.call_optional_args[id(transformed)] = optional_payloads
                self.call_optional_kwargs[id(transformed)] = {}
            return transformed
        if isinstance(node, hir.Block):
            items: list[hir.AST] = []
            for item in node.items:
                transformed = self._transform_node(item)
                if transformed is not None:
                    items.append(transformed)
            return replace(node, items=items)
        if isinstance(node, hir.Declare):
            binding = self.declare_bindings[id(node)]
            if binding.kind in {'function', 'overload'}:
                return None
            if isinstance(node.expr, hir.TypeValue):
                return None
            return replace(
                node,
                expr=self._require_node(self._transform_node(node.expr)),
            )
        if isinstance(node, hir.Return):
            return replace(
                node,
                item=(
                    self._require_node(self._transform_node(node.item))
                    if node.item is not None
                    else None
                ),
            )
        if isinstance(node, hir.Flow):
            return replace(
                node,
                arms=[
                    replace(
                        arm,
                        condition=self._require_node(self._transform_node(arm.condition)),
                        body=self._require_node(self._transform_node(arm.body)),
                    )
                    for arm in node.arms
                ],
                default=(
                    self._require_node(self._transform_node(node.default))
                    if node.default is not None
                    else None
                ),
            )
        if isinstance(node, hir.ShortCircuit):
            return replace(
                node,
                left=self._require_node(self._transform_node(node.left)),
                right=self._require_node(self._transform_node(node.right)),
            )
        if isinstance(node, hir.TypeTest):
            return replace(
                node,
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, hir.Assign):
            return replace(
                node,
                target=self._require_identifier(self._transform_node(node.target)),
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
            transformed = replace(
                node,
                expr=self._require_node(self._transform_node(node.expr)),
            )
            if (
                isinstance(node, (hir.ValueCast, hir.Transmute))
                and isinstance(node.type, ty.QuantityType)
            ):
                return replace(
                    transformed,
                    type=self._lower_runtime_value_type(node.type),
                )
            return transformed
        if isinstance(node, hir.TypeBlock):
            return replace(
                node,
                items=[
                    self._require_node(self._transform_node(item))
                    for item in node.items
                ],
            )
        if isinstance(node, hir.Range):
            originals = [
                *([] if node.step_pair is None else node.step_pair),
                *([] if node.left is None else [node.left]),
                *([] if node.right is None else [node.right]),
            ]
            transformed_by_id = {
                id(item): self._require_node(self._transform_node(item))
                for item in {id(item): item for item in originals}.values()
            }
            return replace(
                node,
                step_pair=(
                    tuple(transformed_by_id[id(item)] for item in node.step_pair)
                    if node.step_pair is not None
                    else None
                ),
                left=(
                    transformed_by_id[id(node.left)]
                    if node.left is not None
                    else None
                ),
                right=(
                    transformed_by_id[id(node.right)]
                    if node.right is not None
                    else None
                ),
            )
        return node

    def _lower_statement_body(self, node: hir.AST) -> hir.AST:
        """Lower expressions contained in a body that is used as a statement."""
        if isinstance(node, hir.Block):
            items: list[hir.AST] = []
            for item in node.items:
                items.extend(self._lower_statement(item))
            return replace(node, items=items)
        statements = self._lower_statement(node)
        if len(statements) == 1:
            return statements[0]
        return hir.Block(node.loc, ty.VOID_TYPE, statements, True)

    def _lower_function_body(self, node: hir.AST, rettype: ty.Type) -> hir.AST:
        """Lower a function body and install labeled-exit signal state when needed."""
        previous_state = (
            self.loop_signal_levels,
            self.loop_signal_kind,
            self.lower_loop_depth,
        )
        uses_nonlocal_exit = self._contains_nonlocal_exit(node)
        if uses_nonlocal_exit:
            self.loop_signal_levels, self.loop_signal_kind = self._new_loop_signals(node)
        else:
            self.loop_signal_levels = None
            self.loop_signal_kind = None
        self.lower_loop_depth = 0

        lowered = self._lower_function_body_inner(node, rettype)
        if uses_nonlocal_exit:
            declarations = self._loop_signal_declarations(node.loc)
            if isinstance(lowered, hir.Block) and lowered.scoped:
                lowered = replace(lowered, items=[*declarations, *lowered.items])
            else:
                lowered = hir.Block(
                    lowered.loc,
                    lowered.type,
                    [*declarations, lowered],
                    True,
                )

        (
            self.loop_signal_levels,
            self.loop_signal_kind,
            self.lower_loop_depth,
        ) = previous_state
        return lowered

    def _lower_function_body_inner(self, node: hir.AST, rettype: ty.Type) -> hir.AST:
        """Make an implicit scalar function result explicit while lowering statements."""
        if rettype == ty.VOID_TYPE or self._contains_return(node):
            return self._lower_statement_body(node)
        if isinstance(node, hir.Block) and node.scoped:
            value_indices = [
                index
                for index, item in enumerate(node.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(node, 'function body does not have one implicit return value')
            value_index = value_indices[0]
            items: list[hir.AST] = []
            for index, item in enumerate(node.items):
                if index != value_index:
                    items.extend(self._lower_statement(item))
                    continue
                if self.current_optional_result is not None:
                    payload = ty.optional_payload(self.current_optional_result.type)
                    if payload is None:
                        raise TypeError('INTERNAL ERROR: missing optional result payload')
                    items.extend(
                        self._optional_write(
                            replace(self.current_optional_result, type='int64'),
                            item,
                            payload,
                        )
                    )
                    items.append(
                        hir.Return(
                            item.loc,
                            ty.BOTTOM_TYPE,
                            hir.Void(item.loc, ty.VOID_TYPE),
                        )
                    )
                    continue
                if self.current_object_result is not None:
                    items.extend(self._object_result_write(item))
                    continue
                prelude, value = self._extract_expression(item)
                items.extend(prelude)
                items.append(hir.Return(value.loc, ty.BOTTOM_TYPE, value))
            return replace(node, type=ty.BOTTOM_TYPE, items=items)
        if self.current_optional_result is not None:
            payload = ty.optional_payload(self.current_optional_result.type)
            if payload is None:
                raise TypeError('INTERNAL ERROR: missing optional result payload')
            statements = [
                *self._optional_write(
                    replace(self.current_optional_result, type='int64'),
                    node,
                    payload,
                ),
                hir.Return(
                    node.loc,
                    ty.BOTTOM_TYPE,
                    hir.Void(node.loc, ty.VOID_TYPE),
                ),
            ]
        elif self.current_object_result is not None:
            statements = self._object_result_write(node)
        else:
            prelude, value = self._extract_expression(node)
            statements = [*prelude, hir.Return(value.loc, ty.BOTTOM_TYPE, value)]
        return hir.Block(node.loc, ty.BOTTOM_TYPE, statements, True)

    @classmethod
    def _contains_nonlocal_exit(cls, node: hir.AST) -> bool:
        """Whether a body contains a break or continue targeting an outer loop."""
        if isinstance(node, (hir.Break, hir.Continue)):
            return node.loop_levels > 0
        if isinstance(node, hir.Block):
            return any(cls._contains_nonlocal_exit(item) for item in node.items)
        if isinstance(node, hir.Flow):
            return any(cls._contains_nonlocal_exit(arm.body) for arm in node.arms) or (
                node.default is not None
                and cls._contains_nonlocal_exit(node.default)
            )
        return False

    @classmethod
    def _contains_return(cls, node: hir.AST) -> bool:
        """Whether a body contains any explicit return site."""
        if isinstance(node, hir.Return):
            return True
        if isinstance(node, hir.Block):
            return any(cls._contains_return(item) for item in node.items)
        if isinstance(node, hir.Flow):
            return any(cls._contains_return(arm.body) for arm in node.arms) or (
                node.default is not None and cls._contains_return(node.default)
            )
        return False

    def _lower_statement(self, node: hir.AST) -> list[hir.AST]:
        """Return target statements, inserting expression-extraction preludes."""
        if isinstance(node, hir.ScopeMetatag):
            return []
        if isinstance(node, hir.Block):
            if not node.scoped:
                statements: list[hir.AST] = []
                for item in node.items:
                    statements.extend(self._lower_statement(item))
                return statements
            return [self._lower_statement_body(node)]
        if isinstance(node, hir.Flow):
            is_loop = any(isinstance(arm, hir.LoopArm) for arm in node.arms)
            if (
                len(node.arms) == 1
                and isinstance(node.arms[0], hir.LoopArm)
                and isinstance(
                    node.arms[0].condition,
                    (hir.IteratorExpression, hir.MultiIteratorExpression),
                )
            ):
                if isinstance(node.arms[0].condition, hir.MultiIteratorExpression):
                    statements = self._lower_multi_iterator_flow(node, node.arms[0])
                else:
                    statements = self._lower_iterator_flow(node, node.arms[0])
            else:
                prelude, flow = self._lower_flow(node)
                statements = [*prelude, flow]
            if (
                is_loop
                and self.lower_loop_depth > 0
                and self.loop_signal_levels is not None
            ):
                statements.extend(self._loop_signal_checkpoint(node.loc))
            return statements
        if isinstance(node, hir.Declare):
            declared_type = node.annotation or node.expr.type
            if (
                isinstance(declared_type, ty.TypeOr)
                and 'undefined' in declared_type.items
                and ty.optional_payload(declared_type) is None
            ):
                self._target_error(
                    node,
                    'heterogeneous runtime union containing `undefined`',
                )
            payload = ty.optional_payload(declared_type)
            if payload is not None:
                cell = hir.ExpressedIdentifier(
                    node.loc,
                    'int64',
                    node.name,
                    binding_id=node.binding_id,
                )
                declaration = replace(
                    node,
                    decltype='let',
                    annotation='int64',
                    expr=self._optional_allocation(node.loc),
                )
                return [
                    declaration,
                    *self._optional_write(cell, node.expr, payload),
                ]
            if isinstance(declared_type, ty.ObjectType):
                return self._lower_object_declare(node, declared_type)
            if self._array_representation(node) == 'stack_data':
                return self._lower_stack_array_declare(node)
            prelude, expr = self._extract_expression(node.expr)
            annotation = (
                'int64'
                if isinstance(
                    node.annotation or node.expr.type,
                    (
                        ty.ArrayType,
                        ty.ObjectType,
                        ty.StringLiteralType,
                        ty.BinaryLiteralType,
                        ty.StringType,
                    ),
                )
                or (
                    isinstance(node.annotation or node.expr.type, str)
                    and (node.annotation or node.expr.type)
                    in {'string', 'grapheme', 'char'}
                )
                else self._lower_runtime_value_type(node.annotation)
                if node.annotation is not None
                else None
            )
            return [
                *prelude,
                replace(
                    node,
                    decltype=(
                        'let'
                        if isinstance(node.expr.type, ty.ArrayType)
                        else node.decltype
                    ),
                    annotation=annotation,
                    expr=expr,
                ),
            ]
        if isinstance(node, hir.IndexAssign):
            target_prelude, target = self._extract_expression(node.target.array)
            stack_data = (
                self._array_use_representation(node.target.array) == 'stack_data'
            )
            index_prelude: list[hir.AST] = []
            index: int | hir.AST = node.target.constant_index
            if index is None:
                index_prelude, index = self._extract_expression(
                    node.target.index
                )
            value_prelude, value = self._array_storage_value(
                node.value,
                node.target.type,
            )
            address = (
                self._pointer_element_address(
                    target,
                    index,
                    self._array_element_layout(node.target.type, node)[0],
                    node.loc,
                )
                if stack_data
                else self._array_element_address(
                    target,
                    index,
                    node.target.type,
                    node.loc,
                )
            )
            cow = (
                self._ensure_mutable_byte_array(target, node.loc)
                if node.target.type == 'uint8' and not stack_data
                else []
            )
            if cow:
                address = self._array_element_address(
                    target,
                    index,
                    node.target.type,
                    node.loc,
                )
            return [
                *target_prelude,
                *index_prelude,
                *value_prelude,
                *cow,
                self._array_store(value, address, node.target.type, node.loc),
            ]
        if isinstance(node, hir.MemberAssign):
            return self._lower_member_assign(node)
        if isinstance(node, hir.Assign):
            if (
                node.target.binding_id is not None
                and node.target.binding_id in self.current_object_field_ids
            ):
                return self._lower_object_field_assign(node)
            if isinstance(node.target.type, ty.ObjectType):
                return self._lower_object_assign(node)
            payload = (
                self.optional_payloads.get(node.target.binding_id)
                if node.target.binding_id is not None
                else None
            )
            if payload is not None:
                cell = replace(node.target, type='int64')
                statements: list[hir.AST] = []
                binding = self.binding_by_semantic_id.get(node.target.binding_id)
                if (
                    self.lowering_module_startup
                    and binding is not None
                    and binding.owner_function is None
                    and node.target.binding_id not in self.optional_globals_initialized
                ):
                    statements.append(
                        hir.Assign(
                            node.loc,
                            ty.VOID_TYPE,
                            cell,
                            '=',
                            self._optional_allocation(node.loc),
                        )
                    )
                    self.optional_globals_initialized.add(node.target.binding_id)
                value = node.value
                if node.op != '=':
                    dunder = {
                        '+=': '__add__',
                        '-=': '__sub__',
                    }.get(node.op)
                    if dunder is None:
                        self._target_error(node, f'optional compound assignment `{node.op}`')
                    function_type = ty.FunctionType(
                        [
                            ty.PosOrKwArg('left', payload),
                            ty.PosOrKwArg('right', payload),
                        ],
                        [],
                        None,
                        payload,
                        [],
                    )
                    value = hir.FunctionCall(
                        node.loc,
                        payload,
                        hir.ExpressedIdentifier(node.loc, function_type, dunder),
                        [
                            self._optional_load_payload(cell, payload, node.loc),
                            node.value,
                        ],
                        {},
                    )
                statements.extend(self._optional_write(cell, value, payload))
                return statements
            prelude, value = self._extract_expression(node.value)
            return [*prelude, replace(node, value=value)]
        if isinstance(node, hir.Return):
            if self.current_object_result is not None:
                if node.item is None:
                    self._target_error(node, 'object return without a value')
                return self._object_result_write(node.item)
            if self.current_optional_result is not None:
                if node.item is None:
                    self._target_error(node, 'optional return without a value')
                payload = ty.optional_payload(node.item.type)
                if payload is None:
                    function_type = self.current_optional_result.type
                    if not isinstance(function_type, ty.TypeOr):
                        raise TypeError('INTERNAL ERROR: missing optional result type')
                    payload = ty.optional_payload(function_type)
                if payload is None:
                    raise TypeError('INTERNAL ERROR: missing optional result payload')
                return [
                    *self._optional_write(
                        replace(self.current_optional_result, type='int64'),
                        node.item,
                        payload,
                    ),
                    hir.Return(node.loc, ty.BOTTOM_TYPE, hir.Void(node.loc, ty.VOID_TYPE)),
                ]
            if node.item is None:
                return [node]
            prelude, item = self._extract_expression(node.item)
            return [*prelude, replace(node, item=item)]
        if isinstance(node, (hir.Break, hir.Continue)):
            if node.loop_levels == 0:
                return [replace(node, label=None)]
            if self.loop_signal_levels is None or self.loop_signal_kind is None:
                self._target_error(node, 'nonlocal loop exit outside a lowered function')
            kind = 1 if isinstance(node, hir.Break) else 2
            return [
                self._loop_signal_assignment(
                    self.loop_signal_levels,
                    node.loop_levels,
                    node.loc,
                ),
                self._loop_signal_assignment(
                    self.loop_signal_kind,
                    kind,
                    node.loc,
                ),
                hir.Break(node.loc, ty.BOTTOM_TYPE),
            ]
        prelude, value = self._extract_expression(node)
        return [*prelude, value]

    def _extract_expression(self, node: hir.AST) -> tuple[list[hir.AST], hir.AST]:
        """Extract statement-valued subexpressions and return a scalar expression."""
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            for base, object_type, field_names in reversed(self.object_literal_contexts):
                if node.binding_id in field_names:
                    return self._extract_literal_field_identifier(
                        node,
                        base,
                        object_type,
                        field_names[node.binding_id],
                    )
        if (
            isinstance(node, hir.ExpressedIdentifier)
            and node.binding_id is not None
            and node.binding_id in self.current_object_field_ids
        ):
            return self._extract_object_field_identifier(node)
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            payload = self.optional_payloads.get(node.binding_id)
            if payload is not None:
                cell = replace(node, type='int64')
                if ty.optional_payload(node.type) is not None:
                    return [], cell
                return [], self._optional_load_payload(cell, payload, node.loc)
        if isinstance(node, hir.ObjectLiteral):
            return self._extract_object_literal(node)
        if isinstance(node, hir.MemberAccess):
            return self._extract_member_access(node)
        if isinstance(node, hir.Undefined):
            self._target_error(node, '`undefined` value without an optional context')
        if isinstance(node, hir.TypeTest):
            prelude, value = self._extract_expression(node.value)
            payload = ty.optional_payload(node.value.type)
            if payload is None and isinstance(node.value, hir.ExpressedIdentifier):
                payload = self.optional_payloads.get(node.value.binding_id)
            system = ty.TypeSystem()
            if payload is None:
                result = system.is_subtype(node.value.type, node.test_type)
                if node.negated:
                    result = not result
                return prelude, hir.Bool(node.loc, 'bool', result)
            payload_matches = system.is_subtype(payload, node.test_type)
            undefined_matches = system.is_subtype('undefined', node.test_type)
            if payload_matches == undefined_matches:
                result = payload_matches
                if node.negated:
                    result = not result
                return prelude, hir.Bool(node.loc, 'bool', result)
            expected_tag = 1 if payload_matches else 0
            if node.negated:
                expected_tag = 1 - expected_tag
            tag = self._optional_tag(value, node.loc)
            return prelude, self._typed_equality(
                tag,
                self._uint8_literal(node.loc, expected_tag),
                'uint8',
                node.loc,
            )
        if isinstance(node, hir.Flow):
            if node.type in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
                self._target_error(node, 'statement-only flow used where a value is required')
            target = self._new_flow_temp(node)
            declaration = hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64' if isinstance(node.type, ty.ArrayType) else node.type,
                self._placeholder(node),
            )
            flow_prelude, flow = self._lower_flow(node, target=target)
            return [declaration, *flow_prelude, flow], target
        if isinstance(node, hir.ShortCircuit):
            return self._extract_expression(self._short_circuit_flow(node))
        if isinstance(node, hir.String):
            return self._extract_string_literal(node)
        if isinstance(node, hir.BasedString):
            return [], replace(node, type='int64')
        if isinstance(node, hir.RepresentationCast):
            return self._extract_representation_cast(node)
        if isinstance(node, hir.StringLength):
            prelude, string = self._extract_expression(node.string)
            if isinstance(node.type, ty.IntegerLiteralType):
                return prelude, self._int64_literal(node.loc, node.type.value)
            return prelude, self._load_i64_field(
                string,
                STRING_GRAPHEME_LENGTH_OFFSET,
                node.loc,
            )
        if isinstance(node, hir.StringIndex):
            return self._extract_string_index(node)
        if isinstance(node, hir.StringSlice):
            return self._extract_string_slice(node)
        if isinstance(node, hir.StringEqual):
            return self._extract_string_equal(node)
        if isinstance(node, hir.StringConcat):
            if isinstance(node.left.type, ty.StringLiteralType) and isinstance(
                node.right.type,
                ty.StringLiteralType,
            ):
                return self._extract_string_literal(
                    hir.String(
                        node.loc,
                        ty.StringLiteralType(
                            node.left.type.value + node.right.type.value
                        ),
                        node.left.type.value + node.right.type.value,
                    )
                )
            self._target_error(node, 'runtime string concatenation and re-segmentation')
        if isinstance(node, hir.InterpolatedString):
            self._target_error(
                node,
                'materializing an interpolated string outside print or printl',
            )
        if isinstance(node, hir.ArrayLiteral):
            return self._extract_array_literal(node)
        if isinstance(node, hir.ArrayLength):
            raw_representation = self._array_use_representation(node.array)
            if raw_representation is not None and isinstance(
                node.type,
                ty.IntegerLiteralType,
            ):
                return [], self._int64_literal(node.loc, node.type.value)
            static_bytes = self._static_binary_array_source(node.array)
            if static_bytes is not None and isinstance(
                node.type,
                ty.IntegerLiteralType,
            ):
                return [], self._int64_literal(node.loc, node.type.value)
            prelude, array = self._extract_expression(node.array)
            if isinstance(node.type, ty.IntegerLiteralType):
                return prelude, self._int64_literal(node.loc, node.type.value)
            return prelude, self._load_i64_field(
                array,
                ARRAY_LENGTH_OFFSET,
                node.loc,
            )
        if isinstance(node, hir.Index):
            raw_representation = self._array_use_representation(node.array)
            static_bytes = self._static_binary_array_source(node.array)
            if raw_representation is not None:
                prelude, array = self._extract_expression(node.array)
            elif static_bytes is not None:
                prelude, array = self._extract_expression(static_bytes)
            else:
                prelude, array = self._extract_expression(node.array)
            index: int | hir.AST = node.constant_index
            if index is None:
                index_prelude, index = self._extract_expression(node.index)
                prelude.extend(index_prelude)
            address = (
                self._pointer_element_address(
                    array,
                    index,
                    self._array_element_layout(node.type, node)[0],
                    node.loc,
                )
                if raw_representation is not None
                else self._pointer_element_address(array, index, 1, node.loc)
                if static_bytes is not None
                else self._array_element_address(
                    array,
                    index,
                    node.type,
                    node.loc,
                )
            )
            return prelude, self._array_load(address, node.type, node.loc)
        if isinstance(node, hir.FunctionCall):
            if self._is_object_method_func(node.func):
                return self._extract_method_call(node)
            prelude: list[hir.AST] = []
            func_prelude, func = self._extract_expression(node.func)
            prelude.extend(func_prelude)
            function_type = (
                node.func.type
                if isinstance(node.func.type, ty.FunctionType)
                else None
            )
            optional_arguments = self.call_optional_args.get(id(node), [])
            pos_args: list[hir.AST] = []
            for index, arg in enumerate(node.pos_args):
                expected_type = (
                    function_type.pos_or_kw[index].type
                    if function_type is not None
                    and index < len(function_type.pos_or_kw)
                    else None
                )
                payload = (
                    optional_arguments[index]
                    if index < len(optional_arguments)
                    else ty.optional_payload(expected_type)
                    if expected_type is not None
                    else None
                )
                boundary = self.array_call_boundary_analyses.get((id(node), index))
                if boundary is not None and boundary.safe:
                    arg_prelude, lowered_arg = self._materialize_array_call_argument(
                        arg,
                        boundary,
                    )
                elif payload is not None:
                    arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
                elif isinstance(arg.type, ty.ObjectType) or isinstance(expected_type, ty.ObjectType):
                    arg_prelude, lowered_arg = self._extract_object_pointer(arg)
                else:
                    arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                pos_args.append(lowered_arg)
            kw_args: dict[str, hir.AST] = {}
            optional_kwargs = self.call_optional_kwargs.get(id(node), {})
            for name, arg in node.kw_args.items():
                payload = optional_kwargs.get(name)
                boundary = self.array_call_boundary_analyses.get((id(node), name))
                if boundary is not None and boundary.safe:
                    arg_prelude, lowered_arg = self._materialize_array_call_argument(
                        arg,
                        boundary,
                    )
                elif payload is not None:
                    arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
                elif isinstance(arg.type, ty.ObjectType):
                    arg_prelude, lowered_arg = self._extract_object_pointer(arg)
                else:
                    arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                kw_args[name] = lowered_arg
            if isinstance(node.type, ty.ObjectType):
                return self._finish_object_call(node, func, pos_args, kw_args, prelude)
            result_payload = ty.optional_payload(node.type)
            if result_payload is not None:
                result = hir.ExpressedIdentifier(
                    node.loc,
                    'int64',
                    self._new_optional_name('result_value'),
                )
                prelude.append(
                    hir.Declare(
                        node.loc,
                        ty.VOID_TYPE,
                        'let',
                        result.name,
                        'int64',
                        self._optional_allocation(node.loc),
                    )
                )
                prelude.append(
                    replace(
                        node,
                        type=ty.VOID_TYPE,
                        func=func,
                        pos_args=[*pos_args, result],
                        kw_args=kw_args,
                    )
                )
                return prelude, replace(result, type=node.type)
            call = replace(node, func=func, pos_args=pos_args, kw_args=kw_args)
            if self._is_eager_bool_logical_call(call):
                eager_args: list[hir.AST] = []
                for arg in call.pos_args:
                    target = self._new_eager_temp(arg)
                    prelude.append(hir.Declare(
                        arg.loc,
                        ty.VOID_TYPE,
                        'let',
                        target.name,
                        'bool',
                        arg,
                    ))
                    eager_args.append(target)
                call = replace(call, pos_args=eager_args)
            return prelude, call
        if isinstance(node, (hir.ValueCast, hir.Transmute)):
            prelude, expr = self._extract_expression(node.expr)
            return prelude, replace(node, expr=expr)
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            prelude, item = self._extract_expression(node.items[0])
            return prelude, replace(node, items=[item])
        return [], node

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
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
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
        left = self._literal_index(node.range.left)
        right = self._literal_index(node.range.right)
        bounds = node.range.bounds or '[]'
        if node.range.left is not None and left is None:
            self._target_error(node.range.left, 'dynamic string slice lower bound')
        if node.range.right is not None and right is None:
            self._target_error(node.range.right, 'dynamic string slice upper bound')
        first_value = (left or 0) + (1 if bounds[0] == '(' else 0)
        first = self._int64_literal(node.loc, first_value)
        if right is None:
            count = self._int64_binary('__sub__', length, first, node.loc)
        else:
            last = right - (1 if bounds[1] == ')' else 0)
            count = self._int64_literal(
                node.loc,
                max(0, last - first_value + 1),
            )
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

    def _lower_stack_array_declare(
        self,
        node: hir.Declare,
    ) -> list[hir.AST]:
        if not isinstance(node.expr, hir.ArrayLiteral):
            prelude, source = self._extract_expression(node.expr)
            return [
                *prelude,
                replace(
                    node,
                    decltype='let',
                    annotation='int64',
                    expr=source,
                ),
            ]
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

    def _extract_array_literal(
        self,
        node: hir.ArrayLiteral,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Allocate fresh backing storage and initialize one array value."""

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
        element_bytes, _signed = self._array_element_layout(
            node.type.element,
            node,
        )
        target = self._new_array_temp(node)
        data_name = self._new_array_name('data')
        data = hir.ExpressedIdentifier(node.loc, 'int64', data_name)
        allocator = (
            '__static_alloca__'
            if self.lowering_module_startup
            else '__alloca__'
        )
        data_allocation = self._intrinsic_call(
            allocator,
            [
                self._int64_literal(
                    node.loc,
                    max(1, node.type.length * element_bytes),
                )
            ],
            'int64',
            node.loc,
        )
        descriptor_allocation = self._intrinsic_call(
            allocator,
            [self._int64_literal(node.loc, ARRAY_DESCRIPTOR_SIZE)],
            'int64',
            node.loc,
        )
        statements: list[hir.AST] = [
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                data_name,
                'int64',
                data_allocation,
            ),
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                descriptor_allocation,
            ),
        ]
        descriptor = replace(target, type='int64')
        statements.extend(
            [
                self._store_i64_field(
                    descriptor,
                    ARRAY_DATA_OFFSET,
                    data,
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    ARRAY_LENGTH_OFFSET,
                    self._int64_literal(node.loc, node.type.length),
                    node.loc,
                ),
                self._store_i64_field(
                    descriptor,
                    ARRAY_CAPACITY_OFFSET,
                    self._int64_literal(node.loc, node.type.length),
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
            ]
        )
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
        return self._extract_expression(node)

    def _optional_allocation(self, loc: Span) -> hir.FunctionCall:
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        return self._intrinsic_call(
            allocator,
            [self._int64_literal(loc, 16)],
            'int64',
            loc,
        )

    def _optional_payload_address(self, cell: hir.AST, loc: Span) -> hir.AST:
        return self._int64_binary(
            '__add__',
            cell,
            self._int64_literal(loc, 8),
            loc,
        )

    @staticmethod
    def _uint8_literal(loc: Span, value: int) -> hir.Integer:
        return hir.Integer(loc, 'uint8', t0.base10, value)

    def _optional_tag(self, cell: hir.AST, loc: Span) -> hir.FunctionCall:
        return self._intrinsic_call('__load_u8__', [cell], 'uint8', loc)

    def _optional_store_payload(
        self,
        value: hir.AST,
        cell: hir.AST,
        payload: ty.TypeExpr,
        loc: Span,
    ) -> hir.FunctionCall:
        address = self._optional_payload_address(cell, loc)
        if payload == 'bool':
            value = hir.Transmute(value.loc, 'uint8', value)
            return self._intrinsic_call('__store_u8__', [value, address], ty.VOID_TYPE, loc)
        layout = ty.fixed_integer_layout(payload)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return self._intrinsic_call(
                f'__store_{prefix}{width}__',
                [value, address],
                ty.VOID_TYPE,
                loc,
            )
        if isinstance(payload, ty.FunctionType):
            value = hir.Transmute(value.loc, 'int64', value)
        return self._intrinsic_call('__store_i64__', [value, address], ty.VOID_TYPE, loc)

    def _optional_load_payload(
        self,
        cell: hir.AST,
        payload: ty.TypeExpr,
        loc: Span,
    ) -> hir.AST:
        address = self._optional_payload_address(cell, loc)
        if payload == 'bool':
            loaded = self._intrinsic_call('__load_i8__', [address], 'int8', loc)
            return hir.Transmute(loc, 'bool', loaded)
        layout = ty.fixed_integer_layout(payload)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return self._intrinsic_call(
                f'__load_{prefix}{width}__',
                [address],
                payload,
                loc,
            )
        loaded = self._intrinsic_call('__load_i64__', [address], 'int64', loc)
        if isinstance(payload, ty.FunctionType):
            return hir.Transmute(
                loc,
                self._lower_callable_type(payload),
                loaded,
            )
        return replace(loaded, type=payload)

    def _optional_write(
        self,
        cell: hir.AST,
        value: hir.AST,
        payload: ty.TypeExpr,
    ) -> list[hir.AST]:
        if isinstance(value, hir.ValueCast):
            return self._optional_write(cell, value.expr, payload)
        if isinstance(value, hir.Flow):
            prelude, flow = self._lower_optional_flow(value, cell, payload)
            return [*prelude, flow]
        def tag_store(tag: int) -> hir.FunctionCall:
            return self._intrinsic_call(
                '__store_u8__',
                [self._uint8_literal(value.loc, tag), cell],
                ty.VOID_TYPE,
                value.loc,
            )
        if isinstance(value, hir.Undefined):
            zero = self._int64_literal(value.loc, 0)
            return [
                tag_store(0),
                self._intrinsic_call(
                    '__store_i64__',
                    [zero, self._optional_payload_address(cell, value.loc)],
                    ty.VOID_TYPE,
                    value.loc,
                ),
            ]
        if ty.optional_payload(value.type) is not None:
            prelude, source = self._extract_expression(value)
            tag = self._optional_tag(source, value.loc)
            payload_value = self._optional_load_payload(source, payload, value.loc)
            return [
                *prelude,
                self._intrinsic_call('__store_u8__', [tag, cell], ty.VOID_TYPE, value.loc),
                self._optional_store_payload(payload_value, cell, payload, value.loc),
            ]
        prelude, payload_value = self._extract_expression(value)
        return [
            *prelude,
            tag_store(1),
            self._optional_store_payload(payload_value, cell, payload, value.loc),
        ]

    def _lower_optional_flow(
        self,
        node: hir.Flow,
        cell: hir.AST,
        payload: ty.TypeExpr,
    ) -> tuple[list[hir.AST], hir.Flow]:
        prelude: list[hir.AST] = []
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, arm in enumerate(node.arms):
            condition_prelude, condition = self._prepare_condition(arm.condition)
            if condition_prelude:
                if isinstance(arm, hir.LoopArm) or index > 0:
                    self._target_error(
                        arm.condition,
                        'optional flow condition requiring extracted statements',
                    )
                prelude.extend(condition_prelude)
            arms.append(
                replace(
                    arm,
                    condition=condition,
                    body=self._optional_flow_body(
                        arm.body,
                        cell,
                        payload,
                    ),
                )
            )
        default = (
            self._optional_flow_body(node.default, cell, payload)
            if node.default is not None
            else None
        )
        return prelude, replace(
            node,
            type=ty.VOID_TYPE,
            arms=arms,
            default=default,
        )

    def _optional_flow_body(
        self,
        body: hir.AST,
        cell: hir.AST,
        payload: ty.TypeExpr,
    ) -> hir.Block:
        if isinstance(body, hir.Block) and body.scoped:
            value_indices = [
                index
                for index, item in enumerate(body.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(body, 'optional branch does not have one value')
            statements: list[hir.AST] = []
            for index, item in enumerate(body.items):
                if index == value_indices[0]:
                    statements.extend(self._optional_write(cell, item, payload))
                else:
                    statements.extend(self._lower_statement(item))
            return replace(body, type=ty.VOID_TYPE, items=statements)
        return hir.Block(
            body.loc,
            ty.VOID_TYPE,
            self._optional_write(cell, body, payload),
            True,
        )

    def _materialize_optional(
        self,
        value: hir.AST,
        payload: ty.TypeExpr,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if ty.optional_payload(value.type) is not None:
            prelude, cell = self._extract_expression(value)
            if isinstance(cell, hir.ExpressedIdentifier):
                return prelude, replace(cell, type='int64')
            target = hir.ExpressedIdentifier(
                value.loc,
                'int64',
                self._new_optional_name('value'),
            )
        else:
            target = hir.ExpressedIdentifier(
                value.loc,
                'int64',
                self._new_optional_name('value'),
            )
            prelude = []
        declaration = hir.Declare(
            value.loc,
            ty.VOID_TYPE,
            'let',
            target.name,
            'int64',
            self._optional_allocation(value.loc),
        )
        return [
            *prelude,
            declaration,
            *self._optional_write(target, value, payload),
        ], target

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

    def _new_array_temp(self, node: hir.ArrayLiteral) -> hir.ExpressedIdentifier:
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

    def _new_default_name(self, role: str) -> str:
        while True:
            name = f'__dewy_default_{role}_{self.next_default_temp}'
            self.next_default_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

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

    def _new_object_temp(self, loc: Span) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_object_{self.next_object_temp}'
            self.next_object_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(loc, 'int64', name)

    def _new_object_name(self, role: str) -> str:
        while True:
            name = f'__dewy_object_{role}_{self.next_object_temp}'
            self.next_object_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    def _new_iterator_temp(
        self,
        node: hir.IteratorExpression,
    ) -> hir.ExpressedIdentifier:
        while True:
            name = f'__dewy_iterator_{self.next_iterator_temp}'
            self.next_iterator_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, 'int64', name)

    def _new_iterator_name(self, role: str) -> str:
        while True:
            name = f'__dewy_iterator_{role}_{self.next_iterator_value}'
            self.next_iterator_value += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    def _new_optional_name(self, role: str) -> str:
        while True:
            name = f'__dewy_optional_{role}_{self.next_optional_temp}'
            self.next_optional_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name

    @staticmethod
    def _intrinsic_call(
        name: str,
        args: list[hir.AST],
        rettype: ty.Type,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [ty.PosOrKwArg(None, arg.type) for arg in args],
            [],
            None,
            rettype,
        )
        return hir.FunctionCall(
            loc,
            rettype,
            hir.ExpressedIdentifier(loc, function_type, name),
            args,
            {},
        )

    @classmethod
    def _int64_binary(
        cls,
        name: Literal[
            '__add__',
            '__sub__',
            '__mul__',
            '__and__',
            '__lshift__',
            '__rshift__',
            '__or__',
        ],
        left: hir.AST,
        right: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'int64'),
                ty.PosOrKwArg('right', 'int64'),
            ],
            [],
            None,
            'int64',
        )
        return hir.FunctionCall(
            loc,
            'int64',
            hir.ExpressedIdentifier(loc, function_type, name),
            [left, right],
            {},
        )

    def _descriptor_address(
        self,
        descriptor: hir.AST,
        offset: int,
        loc: Span,
    ) -> hir.AST:
        if offset == 0:
            return replace(descriptor, type='int64')
        return self._int64_binary(
            '__add__',
            replace(descriptor, type='int64'),
            self._int64_literal(loc, offset),
            loc,
        )

    def _load_i64_field(
        self,
        descriptor: hir.AST,
        offset: int,
        loc: Span,
    ) -> hir.FunctionCall:
        return self._intrinsic_call(
            '__load_i64__',
            [self._descriptor_address(descriptor, offset, loc)],
            'int64',
            loc,
        )

    def _store_i64_field(
        self,
        descriptor: hir.AST,
        offset: int,
        value: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        return self._intrinsic_call(
            '__store_i64__',
            [value, self._descriptor_address(descriptor, offset, loc)],
            ty.VOID_TYPE,
            loc,
        )

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

    def _object_layout(
        self,
        object_type: ty.ObjectType,
        node: hir.AST,
    ) -> tuple[int, dict[str, int]]:
        offset = 0
        align = 1
        offsets: dict[str, int] = {}
        for field in object_type.fields:
            size, field_align = self._field_size_align(field.type, node)
            offset = (offset + field_align - 1) // field_align * field_align
            offsets[field.name] = offset
            offset += size
            align = max(align, field_align)
        size = (offset + align - 1) // align * align if align else offset
        return max(size, 1), offsets

    def _field_size_align(self, type_: ty.Type, node: hir.AST) -> tuple[int, int]:
        if type_ == 'bool':
            return 1, 1
        layout = ty.fixed_integer_layout(type_)
        if layout is not None:
            width, _signed = layout
            size = width // 8
            return size, size
        if self._is_handle_type(type_):
            return 8, 8
        if isinstance(type_, ty.ObjectType):
            size, offsets = self._object_layout(type_, node)
            align = 1
            for field in type_.fields:
                _field_size, field_align = self._field_size_align(field.type, node)
                align = max(align, field_align)
            return size, align
        self._target_error(node, f'object field layout `{type_to_dewy(type_)}`')

    @staticmethod
    def _is_handle_type(type_: ty.Type) -> bool:
        return isinstance(
            type_,
            (
                ty.ArrayType,
                ty.FunctionType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(type_, str)
            and type_ in {'string', 'grapheme', 'char'}
        )

    def _object_allocation(self, loc: Span, size: int) -> hir.FunctionCall:
        allocator = '__static_alloca__' if self.lowering_module_startup else '__alloca__'
        return self._intrinsic_call(
            allocator,
            [self._int64_literal(loc, size)],
            'int64',
            loc,
        )

    def _field_address(self, base: hir.AST, offset: int, loc: Span) -> hir.AST:
        if offset == 0:
            return replace(base, type='int64')
        return self._int64_binary(
            '__add__',
            replace(base, type='int64'),
            self._int64_literal(loc, offset),
            loc,
        )

    def _value_load(self, address: hir.AST, type_: ty.Type, loc: Span) -> hir.AST:
        if isinstance(type_, ty.ObjectType):
            return replace(address, type='int64')
        if type_ == 'bool':
            loaded = self._intrinsic_call('__load_i8__', [address], 'int8', loc)
            return hir.Transmute(loc, 'bool', loaded)
        layout = ty.fixed_integer_layout(type_)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return self._intrinsic_call(
                f'__load_{prefix}{width}__',
                [address],
                type_,
                loc,
            )
        if isinstance(type_, ty.FunctionType):
            loaded = self._intrinsic_call('__load_i64__', [address], 'int64', loc)
            return hir.Transmute(loc, self._lower_callable_type(type_), loaded)
        if self._is_handle_type(type_):
            loaded = self._intrinsic_call('__load_i64__', [address], 'int64', loc)
            return replace(loaded, type=type_)
        self._target_error(address, f'object field load `{type_to_dewy(type_)}`')

    def _value_store(
        self,
        value: hir.AST,
        address: hir.AST,
        type_: ty.Type,
        loc: Span,
    ) -> list[hir.AST]:
        if isinstance(type_, ty.ObjectType):
            return self._object_copy(address, value, type_, loc)
        if type_ == 'bool':
            stored = hir.Transmute(value.loc, 'uint8', value)
            return [self._intrinsic_call('__store_u8__', [stored, address], ty.VOID_TYPE, loc)]
        layout = ty.fixed_integer_layout(type_)
        if layout is not None:
            width, signed = layout
            prefix = 'i' if signed else 'u'
            return [self._intrinsic_call(
                f'__store_{prefix}{width}__',
                [value, address],
                ty.VOID_TYPE,
                loc,
            )]
        if isinstance(type_, ty.FunctionType):
            stored = hir.Transmute(value.loc, 'int64', value)
            return [self._intrinsic_call('__store_i64__', [stored, address], ty.VOID_TYPE, loc)]
        if self._is_handle_type(type_):
            return [
                self._intrinsic_call(
                    '__store_i64__',
                    [value, address],
                    ty.VOID_TYPE,
                    loc,
                )
            ]
        self._target_error(value, f'object field store `{type_to_dewy(type_)}`')

    def _object_copy(
        self,
        dest: hir.AST,
        src: hir.AST,
        object_type: ty.ObjectType,
        loc: Span,
    ) -> list[hir.AST]:
        _size, offsets = self._object_layout(object_type, dest)
        statements: list[hir.AST] = []
        for field in object_type.fields:
            dest_addr = self._field_address(dest, offsets[field.name], loc)
            src_addr = self._field_address(src, offsets[field.name], loc)
            if isinstance(field.type, ty.ObjectType):
                statements.extend(self._object_copy(dest_addr, src_addr, field.type, loc))
            elif isinstance(field.type, ty.FunctionType):
                loaded = self._intrinsic_call(
                    '__load_i64__',
                    [src_addr],
                    'int64',
                    loc,
                )
                statements.append(
                    self._intrinsic_call(
                        '__store_i64__',
                        [loaded, dest_addr],
                        ty.VOID_TYPE,
                        loc,
                    )
                )
            else:
                loaded = self._value_load(src_addr, field.type, loc)
                statements.extend(self._value_store(loaded, dest_addr, field.type, loc))
        return statements

    def _extract_object_literal(
        self,
        node: hir.ObjectLiteral,
        dest: hir.ExpressedIdentifier | None = None,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object literal does not have an object type')
        size, offsets = self._object_layout(node.type, node)
        statements: list[hir.AST] = []
        if dest is None:
            dest = self._new_object_temp(node.loc)
            statements.append(
                hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    dest.name,
                    'int64',
                    self._object_allocation(node.loc, size),
                )
            )
        statements.extend(self._initialize_object_fields(node, dest, offsets))
        return statements, dest

    def _init_object_literal_at(
        self,
        node: hir.ObjectLiteral,
        dest: hir.AST,
    ) -> tuple[list[hir.AST], hir.AST]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object literal does not have an object type')
        _size, offsets = self._object_layout(node.type, node)
        return self._initialize_object_fields(node, dest, offsets), dest

    def _initialize_object_fields(
        self,
        node: hir.ObjectLiteral,
        dest: hir.AST,
        offsets: dict[str, int],
    ) -> list[hir.AST]:
        assert isinstance(node.type, ty.ObjectType)
        field_names = {
            field.binding_id: field.name
            for field in node.fields
            if field.binding_id is not None
        }
        self.object_literal_contexts.append((dest, node.type, field_names))
        statements: list[hir.AST] = []
        try:
            for field in node.fields:
                address = self._field_address(dest, offsets[field.name], field.loc)
                expected = node.type.field(field.name)
                field_type = expected.type if expected is not None else field.value.type
                if (
                    isinstance(field.value, hir.ObjectLiteral)
                    and isinstance(field_type, ty.ObjectType)
                ):
                    nested_prelude, _nested = self._init_object_literal_at(
                        field.value,
                        address,
                    )
                    statements.extend(nested_prelude)
                    continue
                prelude, value = self._extract_expression(field.value)
                statements.extend(prelude)
                statements.extend(
                    self._value_store(value, address, field_type, field.loc)
                )
        finally:
            self.object_literal_contexts.pop()
        return statements

    def _extract_object_pointer(
        self,
        node: hir.AST,
    ) -> tuple[list[hir.AST], hir.AST]:
        if isinstance(node, hir.ObjectLiteral):
            return self._extract_object_literal(node)
        if isinstance(node, hir.MemberAccess) and isinstance(node.type, ty.ObjectType):
            return self._extract_member_access(node)
        if isinstance(node, hir.FunctionCall) and isinstance(node.type, ty.ObjectType):
            return self._extract_expression(node)
        prelude, value = self._extract_expression(node)
        return prelude, value

    def _extract_member_access(
        self,
        node: hir.MemberAccess,
    ) -> tuple[list[hir.AST], hir.AST]:
        prelude, obj = self._extract_object_pointer(node.value)
        if not isinstance(node.value.type, ty.ObjectType):
            self._target_error(node, 'member access requires an object')
        _size, offsets = self._object_layout(node.value.type, node)
        address = self._field_address(obj, offsets[node.name], node.loc)
        field = node.value.type.field(node.name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return prelude, address
        return prelude, self._value_load(address, field_type, node.loc)

    def _extract_object_field_identifier(
        self,
        node: hir.ExpressedIdentifier,
    ) -> tuple[list[hir.AST], hir.AST]:
        if self.current_object_receiver is None or self.current_object_type is None:
            self._target_error(node, 'object field capture without a receiver')
        name = self.current_object_field_names[node.binding_id]
        _size, offsets = self._object_layout(self.current_object_type, node)
        address = self._field_address(self.current_object_receiver, offsets[name], node.loc)
        field = self.current_object_type.field(name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return [], address
        return [], self._value_load(address, field_type, node.loc)

    def _extract_literal_field_identifier(
        self,
        node: hir.ExpressedIdentifier,
        base: hir.AST,
        object_type: ty.ObjectType,
        name: str,
    ) -> tuple[list[hir.AST], hir.AST]:
        _size, offsets = self._object_layout(object_type, node)
        address = self._field_address(base, offsets[name], node.loc)
        field = object_type.field(name)
        field_type = field.type if field is not None else node.type
        if isinstance(field_type, ty.ObjectType):
            return [], address
        return [], self._value_load(address, field_type, node.loc)

    def _is_object_method_func(self, func: hir.AST) -> bool:
        if isinstance(func, hir.MemberAccess) and isinstance(func.type, ty.FunctionType):
            return True
        return (
            isinstance(func, hir.ExpressedIdentifier)
            and func.binding_id is not None
            and func.binding_id in self.current_object_field_ids
            and isinstance(func.type, ty.FunctionType)
        )

    def _method_runtime_type(self, type_: ty.FunctionType) -> ty.FunctionType:
        lowered = self._lower_callable_type(type_)
        assert isinstance(lowered, ty.FunctionType)
        return replace(
            lowered,
            pos_or_kw=[ty.PosOrKwArg(None, 'int64'), *lowered.pos_or_kw],
        )

    def _extract_method_call(
        self,
        node: hir.FunctionCall,
    ) -> tuple[list[hir.AST], hir.AST]:
        func = node.func
        if isinstance(func, hir.MemberAccess):
            if not isinstance(func.value.type, ty.ObjectType):
                self._target_error(node, 'method call requires an object')
            obj_prelude, obj = self._extract_object_pointer(func.value)
            object_type = func.value.type
            name = func.name
            function_type = func.type
        else:
            if self.current_object_receiver is None or self.current_object_type is None:
                self._target_error(node, 'object method call without a receiver')
            obj_prelude, obj = [], self.current_object_receiver
            object_type = self.current_object_type
            assert isinstance(func, hir.ExpressedIdentifier) and func.binding_id is not None
            name = self.current_object_field_names[func.binding_id]
            function_type = func.type
        if not isinstance(function_type, ty.FunctionType):
            self._target_error(node, 'object method is not a function')
        _size, offsets = self._object_layout(object_type, node)
        loaded = hir.Transmute(
            func.loc,
            self._method_runtime_type(function_type),
            self._intrinsic_call(
                '__load_i64__',
                [self._field_address(obj, offsets[name], func.loc)],
                'int64',
                func.loc,
            ),
        )
        prelude = [*obj_prelude]
        pos_args: list[hir.AST] = [replace(obj, type='int64')]
        optional_arguments = self.call_optional_args.get(id(node), [])
        for index, arg in enumerate(node.pos_args):
            expected_type = (
                function_type.pos_or_kw[index].type
                if index < len(function_type.pos_or_kw)
                else None
            )
            payload = (
                optional_arguments[index]
                if index < len(optional_arguments)
                else ty.optional_payload(expected_type)
                if expected_type is not None
                else None
            )
            if payload is not None:
                arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
            elif isinstance(arg.type, ty.ObjectType) or isinstance(expected_type, ty.ObjectType):
                arg_prelude, lowered_arg = self._extract_object_pointer(arg)
            else:
                arg_prelude, lowered_arg = self._extract_expression(arg)
            prelude.extend(arg_prelude)
            pos_args.append(lowered_arg)
        kw_args: dict[str, hir.AST] = {}
        optional_kwargs = self.call_optional_kwargs.get(id(node), {})
        for name, arg in node.kw_args.items():
            payload = optional_kwargs.get(name)
            if payload is not None:
                arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
            elif isinstance(arg.type, ty.ObjectType):
                arg_prelude, lowered_arg = self._extract_object_pointer(arg)
            else:
                arg_prelude, lowered_arg = self._extract_expression(arg)
            prelude.extend(arg_prelude)
            kw_args[name] = lowered_arg
        if isinstance(node.type, ty.ObjectType):
            return self._finish_object_call(
                node,
                loaded,
                pos_args,
                kw_args,
                prelude,
            )
        result_payload = ty.optional_payload(node.type)
        if result_payload is not None:
            result = hir.ExpressedIdentifier(
                node.loc,
                'int64',
                self._new_optional_name('result_value'),
            )
            prelude.append(
                hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    result.name,
                    'int64',
                    self._optional_allocation(node.loc),
                )
            )
            prelude.append(
                replace(
                    node,
                    type=ty.VOID_TYPE,
                    func=loaded,
                    pos_args=[*pos_args, result],
                    kw_args=kw_args,
                )
            )
            return prelude, replace(result, type=node.type)
        call = replace(node, func=loaded, pos_args=pos_args, kw_args=kw_args)
        return prelude, call

    def _finish_object_call(
        self,
        node: hir.FunctionCall,
        func: hir.AST,
        pos_args: list[hir.AST],
        kw_args: dict[str, hir.AST],
        prelude: list[hir.AST],
    ) -> tuple[list[hir.AST], hir.AST]:
        if not isinstance(node.type, ty.ObjectType):
            self._target_error(node, 'object call result is not an object')
        size, _offsets = self._object_layout(node.type, node)
        result = self._new_object_temp(node.loc)
        prelude.append(
            hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                result.name,
                'int64',
                self._object_allocation(node.loc, size),
            )
        )
        prelude.append(
            replace(
                node,
                type=ty.VOID_TYPE,
                func=func,
                pos_args=[*pos_args, result],
                kw_args=kw_args,
            )
        )
        return prelude, result

    def _lower_object_declare(
        self,
        node: hir.Declare,
        object_type: ty.ObjectType,
    ) -> list[hir.AST]:
        if isinstance(node.expr, (hir.ObjectLiteral, hir.FunctionCall)):
            prelude, ptr = self._extract_expression(node.expr)
            return [
                *prelude,
                replace(
                    node,
                    decltype='let',
                    annotation='int64',
                    expr=ptr,
                ),
            ]
        size, _offsets = self._object_layout(object_type, node)
        cell = hir.ExpressedIdentifier(
            node.loc,
            'int64',
            node.name,
            binding_id=node.binding_id,
        )
        declaration = replace(
            node,
            decltype='let',
            annotation='int64',
            expr=self._object_allocation(node.loc, size),
        )
        prelude, src = self._extract_object_pointer(node.expr)
        return [declaration, *prelude, *self._object_copy(cell, src, object_type, node.loc)]

    def _lower_object_assign(self, node: hir.Assign) -> list[hir.AST]:
        if node.op != '=':
            self._target_error(node, f'object compound assignment `{node.op}`')
        if not isinstance(node.target.type, ty.ObjectType):
            self._target_error(node, 'object assignment requires an object')
        dest = replace(node.target, type='int64')
        statements: list[hir.AST] = []
        binding = (
            self.binding_by_semantic_id.get(node.target.binding_id)
            if node.target.binding_id is not None
            else None
        )
        if (
            self.lowering_module_startup
            and binding is not None
            and binding.owner_function is None
            and node.target.binding_id is not None
            and node.target.binding_id not in self.object_globals_initialized
        ):
            size, _offsets = self._object_layout(node.target.type, node)
            statements.append(
                hir.Assign(
                    node.loc,
                    ty.VOID_TYPE,
                    dest,
                    '=',
                    self._object_allocation(node.loc, size),
                )
            )
            self.object_globals_initialized.add(node.target.binding_id)
        prelude, src = self._extract_object_pointer(node.value)
        statements.extend(prelude)
        statements.extend(self._object_copy(dest, src, node.target.type, node.loc))
        return statements

    def _lower_object_field_assign(self, node: hir.Assign) -> list[hir.AST]:
        if node.op != '=':
            self._target_error(node, f'object field compound assignment `{node.op}`')
        if self.current_object_receiver is None or self.current_object_type is None:
            self._target_error(node, 'object field assignment without a receiver')
        assert node.target.binding_id is not None
        name = self.current_object_field_names[node.target.binding_id]
        _size, offsets = self._object_layout(self.current_object_type, node)
        address = self._field_address(
            self.current_object_receiver,
            offsets[name],
            node.loc,
        )
        field = self.current_object_type.field(name)
        field_type = field.type if field is not None else node.target.type
        if isinstance(field_type, ty.ObjectType):
            prelude, src = self._extract_object_pointer(node.value)
            return [*prelude, *self._object_copy(address, src, field_type, node.loc)]
        prelude, value = self._extract_expression(node.value)
        return [*prelude, *self._value_store(value, address, field_type, node.loc)]

    def _lower_member_assign(self, node: hir.MemberAssign) -> list[hir.AST]:
        prelude, obj = self._extract_object_pointer(node.target.value)
        if not isinstance(node.target.value.type, ty.ObjectType):
            self._target_error(node, 'member assignment requires an object')
        _size, offsets = self._object_layout(node.target.value.type, node)
        address = self._field_address(obj, offsets[node.target.name], node.loc)
        field = node.target.value.type.field(node.target.name)
        field_type = field.type if field is not None else node.target.type
        if isinstance(field_type, ty.ObjectType):
            value_prelude, src = self._extract_object_pointer(node.value)
            return [*prelude, *value_prelude, *self._object_copy(address, src, field_type, node.loc)]
        value_prelude, value = self._extract_expression(node.value)
        return [*prelude, *value_prelude, *self._value_store(value, address, field_type, node.loc)]

    def _object_result_write(self, item: hir.AST) -> list[hir.AST]:
        if self.current_object_result is None:
            raise TypeError('INTERNAL ERROR: missing object result cell')
        object_type = self.current_object_result.type
        if not isinstance(object_type, ty.ObjectType):
            raise TypeError('INTERNAL ERROR: object result is not an object type')
        dest = replace(self.current_object_result, type='int64')
        if isinstance(item, hir.ObjectLiteral):
            prelude, _ptr = self._init_object_literal_at(item, dest)
            return [
                *prelude,
                hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
            ]
        prelude, src = self._extract_object_pointer(item)
        return [
            *prelude,
            *self._object_copy(dest, src, object_type, item.loc),
            hir.Return(item.loc, ty.BOTTOM_TYPE, hir.Void(item.loc, ty.VOID_TYPE)),
        ]

    def _lower_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
    ) -> list[hir.AST]:
        """Lower one range iterator to declarations and a counted udewy loop."""

        iterator = arm.condition
        if not isinstance(iterator, hir.IteratorExpression):
            raise TypeError('INTERNAL ERROR: iterator loop has no iterator condition')
        if not isinstance(iterator.iterable, hir.Range):
            return self._lower_string_iterator_flow(node, arm, iterator)
        self._require_finite_udewy_iterator(iterator)
        assert iterator.count is not None
        offset = self._new_iterator_temp(iterator)
        offset_declaration = hir.Declare(
            iterator.loc,
            ty.VOID_TYPE,
            'let',
            offset.name,
            'int64',
            self._int64_literal(iterator.loc, 0),
        )
        target_value = self._iterator_value(
            iterator,
            replace(offset, loc=iterator.loc),
        )
        if isinstance(iterator.target.type, ty.StringType):
            target_declarations, target_updates = self._string_iterator_target(
                iterator,
                target_value,
            )
        else:
            target_declarations = [
                hir.Declare(
                    iterator.target.loc,
                    ty.VOID_TYPE,
                    'let',
                    iterator.target.name,
                    'int64',
                    self._int64_literal(iterator.loc, iterator.first),
                    binding_id=iterator.target.binding_id,
                )
            ]
            target_updates = [
                hir.Assign(
                    iterator.loc,
                    ty.VOID_TYPE,
                    replace(iterator.target, loc=iterator.loc),
                    '=',
                    target_value,
                )
            ]
        increment = hir.Assign(
            iterator.loc,
            ty.VOID_TYPE,
            replace(offset, loc=iterator.loc),
            '+=',
            self._int64_literal(iterator.loc, 1),
        )
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
            [*target_updates, increment, *body_items],
            True,
        )
        condition = self._int64_comparison(
            '__lt__',
            replace(offset, loc=iterator.loc),
            self._int64_literal(iterator.loc, iterator.count),
            iterator.loc,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [hir.LoopArm(arm.loc, ty.VOID_TYPE, condition, body)],
            None,
        )
        return [offset_declaration, *target_declarations, loop]

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

    def _lower_multi_iterator_flow(
        self,
        node: hir.Flow,
        arm: hir.LoopArm,
    ) -> list[hir.AST]:
        condition = arm.condition
        if not isinstance(condition, hir.MultiIteratorExpression):
            raise TypeError('INTERNAL ERROR: multiiterator loop has no composite condition')
        for iterator in condition.iterators:
            if isinstance(iterator.iterable, hir.Range):
                self._require_finite_udewy_iterator(iterator)
        declarations: list[hir.AST] = []
        updates: list[hir.AST] = []
        active_values: list[hir.ExpressedIdentifier] = []
        for iterator in condition.iterators:
            string_iterator = not isinstance(iterator.iterable, hir.Range)
            string_value: hir.AST | None = None
            if string_iterator:
                string_prelude, string_value = self._extract_expression(
                    iterator.iterable
                )
                declarations.extend(string_prelude)
            else:
                assert iterator.count is not None
            offset = self._new_iterator_temp(iterator)
            offset_value = replace(offset, loc=iterator.loc)
            active = hir.ExpressedIdentifier(
                iterator.loc,
                'bool',
                self._new_iterator_name('active'),
            )
            active_values.append(active)
            declarations.extend([
                hir.Declare(
                    iterator.loc,
                    ty.VOID_TYPE,
                    'let',
                    offset.name,
                    'int64',
                    self._int64_literal(iterator.loc, 0),
                ),
                hir.Declare(
                    iterator.loc,
                    ty.VOID_TYPE,
                    'let',
                    active.name,
                    'bool',
                    hir.Bool(iterator.loc, 'bool', False),
                ),
            ])
            payload = ty.optional_payload(iterator.target.type)
            target = replace(iterator.target, loc=iterator.loc)
            value_target: hir.AST = target
            if payload is not None:
                target = replace(target, type='int64')
                declarations.append(
                    hir.Declare(
                        iterator.loc,
                        ty.VOID_TYPE,
                        'let',
                        target.name,
                        'int64',
                        self._optional_allocation(iterator.loc),
                        binding_id=iterator.target.binding_id,
                    )
                )
                declarations.extend(
                    self._optional_write(
                        target,
                        hir.Undefined(iterator.loc, 'undefined'),
                        payload,
                    )
                )
                if string_iterator:
                    value_target = hir.ExpressedIdentifier(
                        iterator.loc,
                        payload,
                        self._new_string_temp(
                            iterator.loc,
                            payload,
                            'iterator_value',
                        ).name,
                    )
                    declarations.append(
                        hir.Declare(
                            iterator.loc,
                            ty.VOID_TYPE,
                            'let',
                            value_target.name,
                            'int64',
                            self._intrinsic_call(
                                '__alloca__',
                                [self._int64_literal(
                                    iterator.loc,
                                    STRING_DESCRIPTOR_SIZE,
                                )],
                                'int64',
                                iterator.loc,
                            ),
                        )
                    )
            else:
                declarations.append(
                    hir.Declare(
                        iterator.loc,
                        ty.VOID_TYPE,
                        'let',
                        target.name,
                        'int64',
                        (
                            self._intrinsic_call(
                                '__alloca__',
                                [
                                    self._int64_literal(
                                        iterator.loc,
                                        STRING_DESCRIPTOR_SIZE,
                                    )
                                ],
                                'int64',
                                iterator.loc,
                            )
                            if string_iterator
                            else self._int64_literal(
                                iterator.loc,
                                iterator.first,
                            )
                        ),
                        binding_id=iterator.target.binding_id,
                    )
                )
                if string_iterator:
                    value_target = target
            active_limit = (
                self._load_i64_field(
                    string_value,
                    STRING_GRAPHEME_LENGTH_OFFSET,
                    iterator.loc,
                )
                if string_value is not None
                else self._int64_literal(iterator.loc, iterator.count)
            )
            active_test = self._int64_comparison(
                '__lt__',
                offset_value,
                active_limit,
                iterator.loc,
            )
            updates.append(
                hir.Assign(
                    iterator.loc,
                    ty.VOID_TYPE,
                    replace(active, loc=iterator.loc),
                    '=',
                    active_test,
                )
            )
            if string_value is not None:
                value = value_target
                value_updates = self._string_iterator_view_updates(
                    string_value,
                    value_target,
                    offset_value,
                    iterator.loc,
                )
            else:
                value = self._iterator_value(iterator, offset_value)
                value_updates = []
            if payload is not None:
                defined_body = [
                    *value_updates,
                    *self._optional_write(target, value, payload),
                    hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        offset_value,
                        '+=',
                        self._int64_literal(iterator.loc, 1),
                    ),
                ]
                exhausted_body = self._optional_write(
                    target,
                    hir.Undefined(iterator.loc, 'undefined'),
                    payload,
                )
            else:
                defined_body = [*value_updates]
                if not string_iterator:
                    defined_body.append(hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        replace(target, type='int64'),
                        '=',
                        value,
                    ))
                defined_body.append(
                    hir.Assign(
                        iterator.loc,
                        ty.VOID_TYPE,
                        offset_value,
                        '+=',
                        self._int64_literal(iterator.loc, 1),
                    )
                )
                exhausted_body = []
            updates.append(
                hir.Flow(
                    iterator.loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            iterator.loc,
                            ty.VOID_TYPE,
                            replace(active, loc=iterator.loc),
                            hir.Block(
                                iterator.loc,
                                ty.VOID_TYPE,
                                defined_body,
                                True,
                            ),
                        )
                    ],
                    (
                        hir.Block(
                            iterator.loc,
                            ty.VOID_TYPE,
                            exhausted_body,
                            True,
                        )
                        if exhausted_body
                        else None
                    ),
                )
            )

        formula_stack: list[hir.AST] = []
        for token in condition.formula:
            if isinstance(token, int):
                formula_stack.append(active_values[token])
                continue
            right = formula_stack.pop()
            left = formula_stack.pop()
            formula_stack.append(
                self._bool_binary(token, left, right, node.loc)
            )
        formula = formula_stack[0]
        self.lower_loop_depth += 1
        lowered_source = self._lower_statement_body(arm.body)
        self.lower_loop_depth -= 1
        source_items = (
            lowered_source.items
            if isinstance(lowered_source, hir.Block)
            else [lowered_source]
        )
        body_gate = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    node.loc,
                    ty.VOID_TYPE,
                    formula,
                    hir.Block(node.loc, ty.VOID_TYPE, source_items, True),
                )
            ],
            hir.Block(
                node.loc,
                ty.BOTTOM_TYPE,
                [hir.Break(node.loc, ty.BOTTOM_TYPE)],
                True,
            ),
        )
        loop_body = hir.Block(
            arm.body.loc,
            ty.VOID_TYPE,
            [*updates, body_gate],
            True,
        )
        loop = hir.Flow(
            node.loc,
            ty.VOID_TYPE,
            [
                hir.LoopArm(
                    arm.loc,
                    ty.VOID_TYPE,
                    hir.Bool(node.loc, 'bool', True),
                    loop_body,
                )
            ],
            None,
        )
        return [*declarations, loop]

    def _require_finite_udewy_iterator(
        self,
        iterator: hir.IteratorExpression,
    ) -> None:
        if iterator.count is None:
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy unbounded range iteration requires bigint lowering',
                pointer_messages=[
                    Pointer(
                        span=iterator.iterable.loc,
                        message=(
                            'this iterator is semantically unbounded and cannot '
                            'use a wrapping int64 counter'
                        ),
                    )
                ],
            ))
        payload = ty.optional_payload(iterator.target.type)
        target_type = payload if payload is not None else iterator.target.type
        values = [
            iterator.first,
            iterator.step,
            iterator.count,
            *([iterator.last] if iterator.last is not None else []),
        ]
        supported_target = target_type == 'int64' or isinstance(
            target_type,
            ty.StringType,
        )
        if not supported_target or not all(
            ty.integer_literal_fits(value, 'int64')
            for value in values
        ):
            raise NotImplementedYet(Error(
                srcfile=self.srcfile,
                title='udewy range iteration requires bigint lowering',
                pointer_messages=[
                    Pointer(
                        span=iterator.iterable.loc,
                        message='this normalized iterator does not fit the int64 ABI',
                    )
                ],
            ))

    def _iterator_value(
        self,
        iterator: hir.IteratorExpression,
        offset: hir.AST,
    ) -> hir.AST:
        scaled_offset = (
            offset
            if iterator.step == 1
            else self._int64_binary(
                '__mul__',
                offset,
                self._int64_literal(iterator.loc, iterator.step),
                iterator.loc,
            )
        )
        return self._int64_binary(
            '__add__',
            self._int64_literal(iterator.loc, iterator.first),
            scaled_offset,
            iterator.loc,
        )

    @staticmethod
    def _bool_binary(
        op: hir.IteratorLogicalOp,
        left: hir.AST,
        right: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'bool'),
                ty.PosOrKwArg('right', 'bool'),
            ],
            [],
            None,
            'bool',
            [],
        )
        base_op: hir.IteratorLogicalOp = {
            'nand': 'and',
            'nor': 'or',
            'xnor': 'xor',
        }.get(op, op)
        call = hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, f'__{base_op}__'),
            [left, right],
            {},
        )
        if op not in {'nand', 'nor', 'xnor'}:
            return call
        unary_type = ty.FunctionType(
            [ty.PosOrKwArg('item', 'bool')],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, unary_type, '__not__'),
            [call],
            {},
        )

    def _lower_flow(
        self,
        node: hir.Flow,
        *,
        target: hir.ExpressedIdentifier | None = None,
    ) -> tuple[list[hir.AST], hir.Flow]:
        """Lower one structured flow, optionally assigning each branch value."""
        prelude: list[hir.AST] = []
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, arm in enumerate(node.arms):
            condition_prelude, condition = self._prepare_condition(arm.condition)
            if condition_prelude:
                if isinstance(arm, hir.LoopArm) or index > 0:
                    self._target_error(
                        arm.condition,
                        'condition requiring extracted statements in this flow position',
                    )
                prelude.extend(condition_prelude)
            if isinstance(arm, hir.LoopArm):
                self.lower_loop_depth += 1
            body = (
                self._assign_flow_body(arm.body, target)
                if target is not None
                else self._lower_statement_body(arm.body)
            )
            if isinstance(arm, hir.LoopArm):
                self.lower_loop_depth -= 1
            arms.append(replace(arm, condition=condition, body=body))
        default = None
        if node.default is not None:
            default = (
                self._assign_flow_body(node.default, target)
                if target is not None
                else self._lower_statement_body(node.default)
            )
        return prelude, replace(node, type=ty.VOID_TYPE if target is not None else node.type, arms=arms, default=default)

    @staticmethod
    def _int64_comparison(
        name: Literal['__lt__'],
        left: hir.AST,
        right: hir.AST,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'int64'),
                ty.PosOrKwArg('right', 'int64'),
            ],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, name),
            [left, right],
            {},
        )

    @staticmethod
    def _typed_equality(
        left: hir.AST,
        right: hir.AST,
        operand_type: ty.TypeExpr,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', operand_type),
                ty.PosOrKwArg('right', operand_type),
            ],
            [],
            None,
            'bool',
            [],
        )
        return hir.FunctionCall(
            loc,
            'bool',
            hir.ExpressedIdentifier(loc, function_type, '__eq__'),
            [left, right],
            {},
        )

    def _prepare_condition(self, node: hir.AST) -> tuple[list[hir.AST], hir.AST]:
        """Preserve lazy boolean operators while lowering their operands."""
        if isinstance(node, hir.ShortCircuit):
            left_prelude, left = self._prepare_condition(node.left)
            right_prelude, right = self._prepare_condition(node.right)
            if right_prelude:
                target = self._new_eager_temp(node)
                declaration = hir.Declare(
                    node.loc,
                    ty.VOID_TYPE,
                    'let',
                    target.name,
                    'bool',
                    hir.Bool(node.loc, 'bool', False),
                )
                false = hir.Bool(node.loc, 'bool', False)
                negated_right = self._typed_equality(
                    right,
                    false,
                    'bool',
                    node.loc,
                )
                if node.op in {'and', 'nand'}:
                    true_value = right if node.op == 'and' else negated_right
                    false_value: hir.AST = (
                        false
                        if node.op == 'and'
                        else hir.Bool(node.loc, 'bool', True)
                    )
                    true_body = hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            *right_prelude,
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                target,
                                '=',
                                true_value,
                            ),
                        ],
                        True,
                    )
                    default = hir.Assign(
                        node.loc,
                        ty.VOID_TYPE,
                        target,
                        '=',
                        false_value,
                    )
                else:
                    true_value = (
                        hir.Bool(node.loc, 'bool', True)
                        if node.op == 'or'
                        else false
                    )
                    right_value = right if node.op == 'or' else negated_right
                    true_body = hir.Assign(
                        node.loc,
                        ty.VOID_TYPE,
                        target,
                        '=',
                        true_value,
                    )
                    default = hir.Block(
                        node.loc,
                        ty.VOID_TYPE,
                        [
                            *right_prelude,
                            hir.Assign(
                                node.loc,
                                ty.VOID_TYPE,
                                target,
                                '=',
                                right_value,
                            ),
                        ],
                        True,
                    )
                flow = hir.Flow(
                    node.loc,
                    ty.VOID_TYPE,
                    [
                        hir.IfArm(
                            node.loc,
                            ty.VOID_TYPE,
                            left,
                            true_body,
                        )
                    ],
                    default,
                )
                return [*left_prelude, declaration, flow], target
            return left_prelude, replace(node, left=left, right=right)
        return self._extract_expression(node)

    def _assign_flow_body(
        self,
        body: hir.AST,
        target: hir.ExpressedIdentifier,
    ) -> hir.AST:
        """Replace a continuing scalar branch result with a temporary assignment."""
        if body.type == ty.BOTTOM_TYPE:
            return self._lower_statement_body(body)
        if isinstance(body, hir.Block) and body.scoped:
            value_indices = [
                index
                for index, item in enumerate(body.items)
                if item.type not in (ty.VOID_TYPE, ty.BOTTOM_TYPE)
            ]
            if len(value_indices) != 1:
                self._target_error(body, 'conditional branch does not have one scalar value')
            value_index = value_indices[0]
            items: list[hir.AST] = []
            for index, item in enumerate(body.items):
                if index != value_index:
                    items.extend(self._lower_statement(item))
                    continue
                prelude, value = self._extract_expression(item)
                items.extend(prelude)
                items.append(self._flow_assignment(target, value))
            return replace(body, type=ty.VOID_TYPE, items=items)
        prelude, value = self._extract_expression(body)
        statements = [*prelude, self._flow_assignment(target, value)]
        return hir.Block(body.loc, ty.VOID_TYPE, statements, True)

    @staticmethod
    def _flow_assignment(
        target: hir.ExpressedIdentifier,
        value: hir.AST,
    ) -> hir.Assign:
        """Build a synthetic assignment to a flow-result temporary."""
        use = replace(target, loc=value.loc)
        return hir.Assign(value.loc, ty.VOID_TYPE, use, '=', value)

    def _new_flow_temp(self, node: hir.AST) -> hir.ExpressedIdentifier:
        """Allocate a deterministic temporary absent from all source bindings."""
        while True:
            name = f'__dewy_flow_{self.next_flow_temp}'
            self.next_flow_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, node.type, name)

    def _new_eager_temp(self, node: hir.AST) -> hir.ExpressedIdentifier:
        """Allocate an argument temporary that forces eager logical-call evaluation."""
        while True:
            name = f'__dewy_eager_{self.next_eager_temp}'
            self.next_eager_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return hir.ExpressedIdentifier(node.loc, 'bool', name)

    def _new_loop_signals(
        self,
        node: hir.AST,
    ) -> tuple[hir.ExpressedIdentifier, hir.ExpressedIdentifier]:
        """Allocate collision-free outward-level and exit-kind signal names."""
        while True:
            ordinal = self.next_loop_signal
            self.next_loop_signal += 1
            levels_name = f'__dewy_loop_levels_{ordinal}'
            kind_name = f'__dewy_loop_kind_{ordinal}'
            if levels_name in self.source_names or kind_name in self.source_names:
                continue
            self.source_names.update({levels_name, kind_name})
            return (
                hir.ExpressedIdentifier(node.loc, 'int64', levels_name),
                hir.ExpressedIdentifier(node.loc, 'int64', kind_name),
            )

    def _loop_signal_declarations(self, loc: Span) -> list[hir.Declare]:
        """Initialize the current function's labeled-exit signals."""
        assert self.loop_signal_levels is not None
        assert self.loop_signal_kind is not None
        zero = self._int64_literal(loc, 0)
        return [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                self.loop_signal_levels.name,
                'int64',
                zero,
            ),
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                self.loop_signal_kind.name,
                'int64',
                replace(zero),
            ),
        ]

    @staticmethod
    def _int64_literal(loc: Span, value: int) -> hir.Integer:
        return hir.Integer(loc, 'int64', t0.base10, value)

    @classmethod
    def _loop_signal_assignment(
        cls,
        target: hir.ExpressedIdentifier,
        value: int,
        loc: Span,
    ) -> hir.Assign:
        return hir.Assign(
            loc,
            ty.VOID_TYPE,
            replace(target, loc=loc),
            '=',
            cls._int64_literal(loc, value),
        )

    @classmethod
    def _loop_signal_condition(
        cls,
        target: hir.ExpressedIdentifier,
        dunder: Literal['__eq__', '__gt__'],
        value: int,
        loc: Span,
    ) -> hir.FunctionCall:
        function_type = ty.FunctionType(
            [
                ty.PosOrKwArg('left', 'int64'),
                ty.PosOrKwArg('right', 'int64'),
            ],
            [],
            None,
            'bool',
            [],
        )
        function = hir.ExpressedIdentifier(loc, function_type, dunder)
        return hir.FunctionCall(
            loc,
            'bool',
            function,
            [
                replace(target, loc=loc),
                cls._int64_literal(loc, value),
            ],
            {},
        )

    def _loop_signal_checkpoint(self, loc: Span) -> list[hir.Flow]:
        """Handle or propagate a pending nonlocal exit after one nested loop."""
        assert self.loop_signal_levels is not None
        assert self.loop_signal_kind is not None

        break_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_kind, 0, loc),
                hir.Break(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        continue_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_kind, 0, loc),
                hir.Continue(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        kind_flow = hir.Flow(
            loc,
            ty.BOTTOM_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_kind,
                        '__eq__',
                        1,
                        loc,
                    ),
                    break_body,
                ),
            ],
            continue_body,
        )
        target_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                self._loop_signal_assignment(self.loop_signal_levels, 0, loc),
                kind_flow,
            ],
            True,
        )
        target_checkpoint = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_levels,
                        '__eq__',
                        1,
                        loc,
                    ),
                    target_body,
                ),
            ],
            None,
        )

        propagate_body = hir.Block(
            loc,
            ty.BOTTOM_TYPE,
            [
                hir.Assign(
                    loc,
                    ty.VOID_TYPE,
                    replace(self.loop_signal_levels, loc=loc),
                    '-=',
                    self._int64_literal(loc, 1),
                ),
                hir.Break(loc, ty.BOTTOM_TYPE),
            ],
            True,
        )
        propagate_checkpoint = hir.Flow(
            loc,
            ty.VOID_TYPE,
            [
                hir.IfArm(
                    loc,
                    ty.BOTTOM_TYPE,
                    self._loop_signal_condition(
                        self.loop_signal_levels,
                        '__gt__',
                        1,
                        loc,
                    ),
                    propagate_body,
                ),
            ],
            None,
        )
        return [target_checkpoint, propagate_checkpoint]

    @staticmethod
    def _is_eager_bool_logical_call(node: hir.FunctionCall) -> bool:
        """Whether target operator syntax needs pre-evaluated direct-call operands."""
        return (
            isinstance(node.func, hir.ExpressedIdentifier)
            and node.func.name in {'__and__', '__or__', '__nand__', '__nor__'}
            and isinstance(node.func.type, ty.FunctionType)
            and all(param.type == 'bool' for param in node.func.type.pos_or_kw)
        )

    def _placeholder(self, node: hir.AST) -> hir.AST:
        """Return an udewy-representable initializer for a flow temporary."""
        if node.type == 'bool':
            return hir.Bool(node.loc, 'bool', False)
        if isinstance(node.type, str) and node.type in {
            'int8',
            'int16',
            'int32',
            'int64',
            'uint8',
            'uint16',
            'uint32',
            'uint64',
        }:
            return hir.Integer(node.loc, node.type, t0.base10, 0)
        if isinstance(node.type, ty.QuantityType):
            runtime_type = self._lower_runtime_value_type(node.type)
            if isinstance(runtime_type, str):
                return hir.Integer(node.loc, runtime_type, t0.base10, 0)
        if isinstance(
            node.type,
            (
                ty.ArrayType,
                ty.StringLiteralType,
                ty.BinaryLiteralType,
                ty.StringType,
            ),
        ) or (
            isinstance(node.type, str)
            and node.type in {'string', 'grapheme', 'char'}
        ):
            return hir.Integer(node.loc, 'int64', t0.base10, 0)
        self._target_error(
            node,
            f'no udewy flow temporary representation for `{type_to_dewy(node.type)}`',
        )

    def _short_circuit_flow(self, node: hir.ShortCircuit) -> hir.Flow:
        """Expand a value-position lazy boolean operator into an equivalent flow."""
        true = hir.Bool(node.loc, 'bool', True)
        false = hir.Bool(node.loc, 'bool', False)
        if node.op == 'and':
            consequent, default = node.right, false
        elif node.op == 'or':
            consequent, default = true, node.right
        elif node.op == 'nand':
            consequent, default = self._bool_not(node.right), true
        else:
            assert node.op == 'nor'
            consequent, default = false, self._bool_not(node.right)
        arm = hir.IfArm(node.loc, 'bool', node.left, consequent)
        return hir.Flow(node.loc, 'bool', [arm], default)

    @staticmethod
    def _bool_not(node: hir.AST) -> hir.FunctionCall:
        """Build the concrete boolean negation used by `nand` and `nor`."""
        function_type = ty.FunctionType(
            [ty.PosOrKwArg('item', 'bool')],
            [],
            None,
            'bool',
            [],
        )
        function = hir.ExpressedIdentifier(node.loc, function_type, '__not__')
        return hir.FunctionCall(node.loc, 'bool', function, [node], {})

    def _target_error(self, node: hir.AST, message: str) -> NoReturn:
        """Report a valid HIR construct unsupported by udewy."""
        raise NotImplementedYet(Error(
            srcfile=self.srcfile,
            title='udewy target cannot lower this construct',
            pointer_messages=[Pointer(span=node.loc, message=message)],
        ))

    @staticmethod
    def _require_node(node: hir.AST | None) -> hir.AST:
        """Narrow a transformed expression that is not allowed to be elided."""
        if node is None:
            raise ValueError('INTERNAL ERROR: unexpectedly elided expression')
        return node

    @staticmethod
    def _require_identifier(node: hir.AST | None) -> hir.ExpressedIdentifier:
        """Narrow a transformed assignment target to an identifier."""
        if not isinstance(node, hir.ExpressedIdentifier):
            raise TypeError('INTERNAL ERROR: assignment target is not an identifier')
        return node


def lower_for_udewy(root: hir.AST, srcfile: SrcFile) -> LoweredProgram:
    """Legalize checked HIR function constructs for udewy source emission."""
    if not isinstance(root, hir.Block):
        raise TypeError(f'expected Block, got {type(root).__name__}')
    return _Lowerer(root, srcfile).lower()
