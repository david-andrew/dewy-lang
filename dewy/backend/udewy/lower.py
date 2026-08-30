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
from dataclasses import fields, is_dataclass, replace
from typing import Literal, NoReturn

from ...parser import t0
from ...reporting import Error, Pointer, Span, SrcFile
from ...semantic import builtins, hir, ty
from ...semantic.analyze.effects import ProgramEffects, analyze_effects
from ...semantic.errors import NotImplementedYet
from ...semantic.hir_display import type_to_dewy
from .lowering_arrays import _ArrayLowering
from .lowering_dicts import _DictLowering
from .lowering_flow import _FlowLowering
from .lowering_iterators import _IteratorLowering
from .lowering_objects import _ObjectLowering
from .lowering_optionals import _OptionalLowering
from .lowering_places import _PlaceLowering
from .lowering_shared import (
    ARRAY_LENGTH_OFFSET,
    STRING_GRAPHEME_LENGTH_OFFSET,
    ArrayCallBoundaryAnalysis,
    ArrayParameterAnalysis,
    ArrayRepresentation,
    ArrayUse,
    LoweredFunction,
    LoweredProgram,
    StringResultBound,
    _Binding,
    _FunctionDef,
    _Scope,
    FIXED_INTEGER_WIDTHS,
)
from .lowering_strings import _StringLowering


def _erase_dimensions(root: object) -> None:
    """Physical dimensions and refinements have no runtime representation.

    Every node and annotation typed as a quantity is retyped in place by its
    numeric representation, so the rest of the lowering never sees a
    ``QuantityType``. Nodes are mutated (not replaced) because the checker's
    side tables are keyed by node identity.
    """
    seen: set[int] = set()

    def erase(type_: object) -> object:
        if isinstance(type_, ty.RefinedType):
            type_ = type_.base  # refinements were proven during checking
        if isinstance(type_, ty.TypeOr):
            # `rational * Length | Overflow`: the members lose their dimensions too
            members = [erase(member) for member in type_.items]
            return type_ if all(a is b for a, b in zip(members, type_.items)) else ty.TypeOr(members)
        return type_.number if isinstance(type_, ty.QuantityType) else type_

    def walk(value: object) -> None:
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if not is_dataclass(value) or isinstance(value, type) or id(value) in seen:
            return
        if type(value).__module__ == ty.__name__:
            return  # types are immutable; only node fields get rewritten
        seen.add(id(value))
        for field_info in fields(value):
            current = getattr(value, field_info.name)
            if field_info.name in {'type', 'annotation'}:
                erased = erase(current)
                if erased is not current:
                    setattr(value, field_info.name, erased)
                continue
            walk(current)

    walk(root)


class _Lowerer(
    _DictLowering,
    _StringLowering,
    _ArrayLowering,
    _ObjectLowering,
    _PlaceLowering,
    _OptionalLowering,
    _IteratorLowering,
    _FlowLowering,
):
    """Discover callable units, validate captures, and rewrite them for udewy."""

    def __init__(self, root: hir.Block, srcfile: SrcFile, entry_name: str = 'main'):
        """Initialize per-program identity maps and deterministic counters."""
        _erase_dimensions(root)
        self.root = root
        self.srcfile = srcfile
        self.preserve_raw_udewy_shifts = bool(re.search(
            r'(?m)^\s*\$no_prelude\s*=\s*true\b',
            srcfile.body,
        ))
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
        self.next_shift_temp = 1
        self.next_range_temp = 1
        self.next_array_temp = 1
        self.next_string_temp = 1
        self.next_object_temp = 1
        self.next_iterator_temp = 1
        self.next_iterator_value = 1
        self.next_optional_temp = 1
        self.next_result_temp = 1
        self.next_default_temp = 1
        self.next_place_temp = 1
        self.next_loop_signal = 1
        self.loop_signal_levels: hir.ExpressedIdentifier | None = None
        self.loop_signal_kind: hir.ExpressedIdentifier | None = None
        self.lower_loop_depth = 0
        self.lowering_module_startup = False
        self.optional_payloads: dict[int, ty.TypeExpr] = {}
        self.union_cells: dict[int, tuple[ty.TypeExpr, ...]] = {}
        # Unicode property tables referenced by lowered code: one hidden
        # global per table, declared once and stored at module startup
        self.unicode_table_globals: dict[str, hir.BasedString] = {}
        # bindings whose value is an enum (a union of singletons): a word
        # holding the member index (`ty.enum_members`), no cell
        self.enum_words: dict[int, tuple[ty.TypeExpr, ...]] = {}
        self.named_copy_symbols: dict[int, str] = {}  # recursive alias id -> deep-copy function symbol
        self.pending_named_copies: list[ty.NamedType] = []
        self.optional_globals_initialized: set[int] = set()
        self.union_globals_initialized: set[int] = set()
        self.object_globals_initialized: set[int] = set()
        self.call_optional_args: dict[int, list[ty.TypeExpr | None]] = {}
        self.call_union_args: dict[int, list[tuple[ty.TypeExpr, ...] | None]] = {}
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
        # lambda lifting: a local function reading enclosing locals receives
        # them as trailing hidden parameters; every direct call passes them
        self.lifted: dict[int, list[_Binding]] = {}          # id(function) -> captured bindings
        self.lifted_types: dict[int, ty.Type] = {}           # id(binding) -> runtime parameter type
        self.direct_calls: list[tuple[_FunctionDef | None, hir.FunctionCall]] = []
        self.callee_nodes: set[int] = set()                  # ids of nodes in callee position
        self.identifier_nodes: dict[int, hir.ExpressedIdentifier] = {}
        self.array_call_boundary_analyses: dict[
            tuple[int, int | str],
            ArrayCallBoundaryAnalysis,
        ] = {}
        self.array_result_destinations: dict[int, hir.ExpressedIdentifier] = {}
        self.object_result_destinations: dict[int, hir.ExpressedIdentifier] = {}
        # union-returning calls whose result cell is a fresh destination (a
        # declared binding, the enclosing function's result cell): the call
        # writes there directly instead of into a temporary that is then
        # deep-copied
        self.union_result_destinations: dict[int, hir.ExpressedIdentifier] = {}
        self.current_optional_result: hir.ExpressedIdentifier | None = None
        self.current_object_result: hir.ExpressedIdentifier | None = None
        self.current_array_result: hir.ExpressedIdentifier | None = None
        self.current_string_result: hir.ExpressedIdentifier | None = None
        self.current_union_result: hir.ExpressedIdentifier | None = None
        self.current_dynamic_array_result: ty.ArrayType | None = None
        self.string_result_bounds: dict[int, StringResultBound | None] = {}
        self.string_result_needs_dest: set[int] = set()
        self.string_result_call_targets: dict[int, _FunctionDef] = {}
        # Side tables above are keyed by ``id(node)``. CPython reuses the id
        # of a freed object, so every node registered as a key must stay
        # alive for the whole lowering or a later node could inherit stale
        # analyses (this manifested as a boolean argument being cloned as an
        # array, depending on allocator state).
        self._keyed_nodes_keepalive: list[object] = []
        self.current_place_parameter_cells: dict[
            int,
            hir.ExpressedIdentifier,
        ] = {}
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
        # the source function the entry wrapper calls: `main`, or the generated test runner
        self.entry_name = entry_name
        self.program_effects: ProgramEffects = analyze_effects(root)

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
        self._analyze_string_results()
        self._check_captures()
        self.user_main_takes_argv = any(
            isinstance(item, hir.Declare)
            and item.name == self.entry_name
            and isinstance(item.expr, hir.FunctionLiteral)
            and bool(item.expr.pos_or_kw_args)
            for item in self.root.items
        )
        self.needs_startup = self.user_main_takes_argv or self.entry_name != 'main' or any(
            not (
                isinstance(item, hir.Declare)
                and (
                    (
                        (binding := self.declare_bindings.get(id(item))) is not None
                        and binding.kind in {'function', 'overload'}
                    )
                    or isinstance(item.expr, (hir.TypeValue, hir.GenericFunction))
                    or self._zero_initialized_scalar_global(item)
                    or self._is_range_valued(item.annotation or item.expr.type)
                    or self._is_compile_time_rational(item.annotation or item.expr.type)
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
        lowered_functions.extend(self._synthesize_named_copies())

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
                storage = self._global_storage(transformed)
                globals_.append(storage)
                if self._zero_initialized_scalar_global(transformed):
                    continue   # `let cursor:int64 = 0`: inert storage already holds the value
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
        main = self.module_scope.bindings.get(self.entry_name)
        argv_prologue: list[hir.AST] | None = None
        argv_value: hir.AST | None = None
        if self.user_main_takes_argv:
            argv_prologue, argv_value = self._build_argv_prologue(self.root.loc)
        user_main_symbol = (
            main.function.symbol
            if main is not None and main.function is not None
            else None
        )
        # module startup may have requested more copy functions
        lowered_functions.extend(self._synthesize_named_copies())
        for name, data in self.unicode_table_globals.items():
            # a packed byte literal is a constant initializer: no startup needed
            globals_.append(hir.Declare(self.root.loc, ty.VOID_TYPE, 'let', name, 'int64', data))
        return LoweredProgram(
            lowered_functions,
            globals_,
            startup_items,
            user_main_symbol,
            self.startup_symbol,
            self.needs_startup,
            argv_prologue,
            argv_value,
        )

    def _lower_function(self, function: _FunctionDef) -> LoweredFunction:
        literal = function.literal
        if isinstance(literal.rettype, ty.RefinedType):
            # a refined result is proven at every return during checking; the target sees the base type
            literal = replace(literal, rettype=literal.rettype.base)
        if literal.rest_args is not None:
            self._target_error(literal, 'rest parameters and argument spreading')
        result_payload = ty.optional_payload(literal.rettype)
        object_result = isinstance(literal.rettype, ty.ObjectType)
        array_result = (
            isinstance(literal.rettype, ty.ArrayType)
            and literal.rettype.length is not None
        )
        if (
            array_result
            and isinstance(literal.rettype, ty.ArrayType)
            and not self._array_result_elements_are_returnable(literal.rettype)
        ):
            self._target_error(
                literal,
                'exact array returns require a recursively fixed result layout',
            )
        if (
            object_result
            and isinstance(literal.rettype, ty.ObjectType)
            and not self._object_result_fields_are_returnable(literal.rettype)
        ):
            self._target_error(
                literal,
                'object returns require a recursively fixed result layout',
            )
        if isinstance(result_payload, ty.ArrayType):
            self._target_error(
                literal,
                'optional array returns require array ownership lowering',
            )
        string_result = id(function) in self.string_result_needs_dest
        union_result = ty.runtime_union_members(literal.rettype) is not None
        dynamic_array_result = (
            literal.rettype
            if isinstance(literal.rettype, ty.ArrayType)
            and literal.rettype.length is None
            else None
        )
        rettype = (
            ty.VOID_TYPE
            if result_payload is not None
            or object_result
            or array_result
            or string_result
            or union_result
            else self._target_scalar_type(literal.rettype, literal)
        )
        lowered_pos: list[hir.Param | hir.BoundParam] = []
        default_prologue: list[hir.AST] = []
        parameter_prologue: list[hir.AST] = []
        place_parameter_cells: dict[int, hir.ExpressedIdentifier] = {}

        def lower_param(param: hir.Param) -> hir.Param:
            # a union with `undefined` and several other members is an ordinary
            # general union (`undefined` is member 0, so its tag matches optionals)
            if param.place:
                if param.binding_id is None:
                    raise TypeError(
                        'INTERNAL ERROR: place parameter has no binding identity'
                    )
                incoming_name = self._new_place_name(param.name)
                incoming = hir.ExpressedIdentifier(
                    literal.loc,
                    'int64',
                    incoming_name,
                )
                direct_storage = (
                    isinstance(param.type, ty.ObjectType)
                    or ty.optional_payload(param.type) is not None
                )
                if not direct_storage:
                    place_parameter_cells[param.binding_id] = incoming
                runtime_type = (
                    'int64'
                    if direct_storage
                    else self._place_runtime_type(param.type, literal)
                )
                initial_value = (
                    incoming
                    if direct_storage
                    else self._value_load(incoming, runtime_type, literal.loc)
                )
                parameter_prologue.append(hir.Declare(
                    literal.loc,
                    ty.VOID_TYPE,
                    'let',
                    param.name,
                    runtime_type,
                    initial_value,
                    binding_id=param.binding_id,
                ))
                return replace(
                    param,
                    name=incoming_name,
                    type='int64',
                    binding_id=None,
                    place=False,
                )
            if isinstance(param.type, ty.ObjectType):
                incoming_name = self._new_object_name(f'arg_{param.name}')
                incoming = hir.ExpressedIdentifier(
                    literal.loc,
                    'int64',
                    incoming_name,
                )
                summary = (
                    self.program_effects.for_param_binding(param.binding_id)
                    if param.binding_id is not None
                    else None
                )
                if summary is not None and summary.read_only:
                    # The body provably never writes to or retains the object,
                    # so the parameter borrows the caller's storage instead of
                    # copying it into a fresh allocation.
                    parameter_prologue.append(hir.Declare(
                        literal.loc,
                        ty.VOID_TYPE,
                        'let',
                        param.name,
                        'int64',
                        incoming,
                        binding_id=param.binding_id,
                    ))
                    return replace(
                        param,
                        name=incoming_name,
                        type='int64',
                        binding_id=None,
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
            members = ty.runtime_union_members(param.type)
            if members is not None:
                incoming_name = self._new_optional_name(f'arg_{param.name}')
                incoming = hir.ExpressedIdentifier(
                    literal.loc,
                    param.type,
                    incoming_name,
                )
                summary = (
                    self.program_effects.for_param_binding(param.binding_id)
                    if param.binding_id is not None
                    else None
                )
                if summary is not None and summary.read_only:
                    # As for objects: a body that never writes to or retains
                    # the value borrows the caller's cell (`0 | [...]` values
                    # are otherwise deep-copied — tree and limb arrays — on
                    # every call).
                    parameter_prologue.append(hir.Declare(
                        literal.loc,
                        ty.VOID_TYPE,
                        'let',
                        param.name,
                        'int64',
                        replace(incoming, type='int64'),
                        binding_id=param.binding_id,
                    ))
                    return replace(
                        param,
                        name=incoming_name,
                        type='int64',
                        binding_id=None,
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
                        self._union_cell_allocation(members, literal.loc),
                        binding_id=param.binding_id,
                    )
                )
                parameter_prologue.extend(
                    self._union_prepare_trees(cell, members, literal.loc)
                )
                parameter_prologue.extend(
                    self._union_write(cell, incoming, members)
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

        for param in [*literal.pos_or_kw_args, *literal.kw_only_args]:
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
            if isinstance(param.type, ty.ArrayType):
                selected = hir.Flow(
                    literal.loc,
                    param.type,
                    [
                        hir.IfArm(
                            literal.loc,
                            param.type,
                            hir.ExpressedIdentifier(
                                literal.loc,
                                'bool',
                                present_name,
                            ),
                            incoming,
                        )
                    ],
                    default,
                )
                default_prologue.append(hir.Declare(
                    literal.loc,
                    ty.VOID_TYPE,
                    'let',
                    param.name,
                    param.type,
                    selected,
                    binding_id=param.binding_id,
                ))
                continue
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
        for binding in self.lifted.get(id(function), []):
            lowered_pos.append(hir.Param(binding.emitted_name or binding.name, self.lifted_types[id(binding)]))
        receiver = None
        if literal.object_receiver:
            receiver_name = self._new_object_name('self')
            receiver = hir.ExpressedIdentifier(literal.loc, 'int64', receiver_name)
            lowered_pos = [hir.Param(receiver_name, 'int64'), *lowered_pos]
        result_target = None
        object_result_target = None
        array_result_target = None
        string_result_target = None
        union_result_target = None
        if (
            result_payload is not None
            or object_result
            or array_result
            or string_result
            or union_result
        ):
            assert function.result_name is not None
            lowered_pos.append(
                hir.Param(function.result_name, 'int64')
            )
            target = hir.ExpressedIdentifier(
                literal.loc,
                literal.rettype,
                function.result_name,
            )
            if object_result:
                object_result_target = target
            elif array_result:
                array_result_target = target
            elif string_result:
                string_result_target = target
            elif union_result:
                union_result_target = target
            else:
                result_target = target
        previous_result = self.current_optional_result
        previous_object_result = self.current_object_result
        previous_array_result = self.current_array_result
        previous_string_result = self.current_string_result
        previous_union_result = self.current_union_result
        previous_dynamic_array_result = self.current_dynamic_array_result
        previous_place_parameter_cells = self.current_place_parameter_cells
        previous_receiver = self.current_object_receiver
        previous_object_type = self.current_object_type
        previous_field_ids = self.current_object_field_ids
        previous_field_names = self.current_object_field_names
        self.current_optional_result = result_target
        self.current_object_result = object_result_target
        self.current_array_result = array_result_target
        self.current_string_result = string_result_target
        self.current_union_result = union_result_target
        self.current_dynamic_array_result = dynamic_array_result
        self.current_place_parameter_cells = place_parameter_cells
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
        self.current_array_result = previous_array_result
        self.current_string_result = previous_string_result
        self.current_union_result = previous_union_result
        self.current_dynamic_array_result = previous_dynamic_array_result
        self.current_place_parameter_cells = previous_place_parameter_cells
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
        if self.lifted.get(id(function)) and isinstance(function_type, ty.FunctionType):
            function_type = replace(
                function_type,
                pos_or_kw=[*function_type.pos_or_kw, *(ty.PosOrKwArg(None, self.lifted_types[id(binding)]) for binding in self.lifted[id(function)])],
            )
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

    @staticmethod
    def _is_compile_time_rational(type_: object) -> bool:
        number = type_.number if isinstance(type_, ty.QuantityType) else type_
        return isinstance(number, ty.RationalLiteralType)

    @staticmethod
    def _is_range_valued(type_: object) -> bool:
        return type_ == 'range' or (
            isinstance(type_, ty.TypeParameterize) and type_.t == 'range'
        )

    def _lower_callable_type(self, type_: ty.Type) -> ty.Type:
        if not isinstance(type_, ty.FunctionType):
            return type_
        pos: list[ty.PosOrKwArg] = []
        for param in type_.pos_or_kw:
            pos.append(ty.PosOrKwArg(
                param.name,
                (
                    'int64'
                    if param.place
                    else self._lower_runtime_value_type(param.type)
                ),
            ))
            if not param.required:
                pos.append(ty.PosOrKwArg(None, 'bool'))
        for param in type_.kw_only:
            pos.append(ty.PosOrKwArg(
                param.name,
                (
                    'int64'
                    if param.place
                    else self._lower_runtime_value_type(param.type)
                ),
            ))
            if not param.required:
                pos.append(ty.PosOrKwArg(None, 'bool'))
        rettype: ty.TypeExpr = self._lower_runtime_value_type(type_.ret)
        if (
            isinstance(type_.ret, ty.ObjectType)
            or ty.optional_payload(type_.ret) is not None
            or (
                isinstance(type_.ret, ty.ArrayType)
                and type_.ret.length is not None
            )
        ):
            pos.append(ty.PosOrKwArg(None, 'int64'))
            rettype = ty.VOID_TYPE
        return replace(
            type_,
            pos_or_kw=pos,
            kw_only=[],
            rest=None,
            ret=rettype,
        )

    def _extract_or_throw(self, node: hir.OrThrow) -> tuple[list[hir.AST], hir.AST]:
        """`value or_throw`: materialize the value's cell under the hidden
        binding, return the exception alternatives, continue narrowed."""
        loc = node.loc
        value_type = node.value.type
        members = ty.runtime_union_members(value_type)
        if members is not None:
            prelude, cell = self._materialize_union(node.value, members)
            self.union_cells[node.binding_id] = members
        else:
            payload = ty.optional_payload(value_type)
            if payload is None:
                self._target_error(node, '`or_throw` on a value that is not a runtime union')
            prelude, cell = self._materialize_optional(node.value, payload)
            self.optional_payloads[node.binding_id] = payload
        holder = hir.Declare(loc, ty.VOID_TYPE, 'let', node.name, 'int64', replace(cell, type='int64'), binding_id=node.binding_id)
        tested = hir.ExpressedIdentifier(loc, value_type, node.name, binding_id=node.binding_id)
        test_prelude, test = self._extract_expression(hir.TypeTest(loc, 'bool', tested, node.exception_type, False))
        propagate = self._lower_statement(hir.Return(loc, ty.BOTTOM_TYPE, node.propagated))
        flow = hir.Flow(loc, ty.VOID_TYPE, [hir.IfArm(loc, ty.VOID_TYPE, test, hir.Block(loc, ty.VOID_TYPE, propagate, True))], None)
        result = hir.ExpressedIdentifier(loc, node.type, node.name, binding_id=node.binding_id)
        result_prelude, value = self._extract_expression(result)
        return [*prelude, holder, *test_prelude, flow, *result_prelude], value

    def _hold_union_value(self, value: hir.AST, name: str, binding_id: int, loc: Span) -> tuple[list[hir.AST], tuple[ty.TypeExpr, ...]]:
        """Materialize a union/optional value's cell under a hidden binding and
        register its storage members; returns the statements and the members."""
        members = ty.runtime_union_members(value.type)
        if members is not None:
            prelude, cell = self._materialize_union(value, members)
            self.union_cells[binding_id] = members
        else:
            payload = ty.optional_payload(value.type)
            if payload is None:
                self._target_error(value, 'a union operand that is not a runtime union')
            prelude, cell = self._materialize_optional(value, payload)
            self.optional_payloads[binding_id] = payload
            members = ('undefined', payload)
        holder = hir.Declare(loc, ty.VOID_TYPE, 'let', name, 'int64', replace(cell, type='int64'), binding_id=binding_id)
        return [*prelude, holder], members

    def _extract_forwarding_access(self, node: hir.ForwardingAccess) -> tuple[list[hir.AST], hir.AST]:
        """Safe navigation: read the member from an ordinary alternative, else
        retag the exception alternative into the result union."""
        loc = node.loc
        statements, members = self._hold_union_value(node.value, node.name, node.binding_id, loc)
        system = ty.TypeSystem()
        result_members = ty.runtime_union_members(node.type)
        result = hir.ExpressedIdentifier(loc, 'int64', self._new_optional_name('forwarded'))
        if result_members is not None:
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', result.name, 'int64', self._union_cell_allocation(result_members, loc)))
            statements.extend(self._union_prepare_trees(result, result_members, loc))
            def write(value: hir.AST) -> list[hir.AST]:
                return self._union_write(result, value, result_members)
        elif ty.optional_payload(node.type) is not None:
            payload = ty.optional_payload(node.type)
            assert payload is not None
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', result.name, 'int64', self._optional_allocation(loc)))
            def write(value: hir.AST) -> list[hir.AST]:
                return self._optional_write(result, value, payload)
        else:
            # every alternative has the member at one type: a plain value
            result = hir.ExpressedIdentifier(loc, self._lower_runtime_value_type(node.type), self._new_optional_name('common'))
            statements.append(hir.Declare(loc, ty.VOID_TYPE, 'let', result.name, result.type, self._placeholder(replace(node, type=node.type))))
            def write(value: hir.AST) -> list[hir.AST]:
                prelude, lowered = self._extract_expression(value)
                return [*prelude, hir.Assign(loc, ty.VOID_TYPE, result, '=', lowered)]
        tag = self._optional_tag(hir.ExpressedIdentifier(loc, 'int64', node.name), loc)
        arms: list[hir.IfArm | hir.LoopArm] = []
        for index, member in enumerate(members):
            if system.is_subtype(member, ty.EXCEPTION_TYPE):
                continue
            unfolded = ty.unfold(member)
            assert isinstance(unfolded, ty.ObjectType)
            field = unfolded.field(node.field)
            assert field is not None
            receiver = hir.ExpressedIdentifier(loc, unfolded, node.name, binding_id=node.binding_id)
            access = hir.MemberAccess(loc, field.type, receiver, node.field)
            arms.append(hir.IfArm(
                loc, ty.VOID_TYPE,
                self._typed_equality(tag, self._uint8_literal(loc, index), 'uint8', loc),
                hir.Block(loc, ty.VOID_TYPE, write(access), True),
            ))
        # the exception alternatives forward: the receiver's cell, viewed as its
        # exception subset, retags into the result
        if node.exception_type == ty.BOTTOM_TYPE:
            # common-member access on an ordinary union: some arm always matches
            statements.append(hir.Flow(loc, ty.VOID_TYPE, arms, None))
            return statements, result
        forwarded: hir.AST
        if node.exception_type == 'undefined':
            forwarded = hir.Undefined(loc, 'undefined')
        else:
            forwarded = hir.ExpressedIdentifier(loc, node.exception_type, node.name, binding_id=node.binding_id)
        statements.append(hir.Flow(loc, ty.VOID_TYPE, arms, hir.Block(loc, ty.VOID_TYPE, write(forwarded), True)))
        return statements, result

    def _lower_runtime_value_type(self, type_: ty.TypeExpr) -> ty.TypeExpr:
        if ty.optional_payload(type_) is not None:
            return 'int64'
        if ty.is_user_nominal(type_):
            return 'int64'  # a unit-like error is a word (its union tag carries the identity)
        if ty.runtime_union_members(type_) is not None:
            return 'int64'
        if ty.enum_members(type_) is not None:
            return 'int64'   # an enum is its member index
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
        if ty.is_user_nominal(type_):
            return 'int64'
        if ty.enum_members(type_) is not None:
            return 'int64'   # an enum result is its tag word
        if ty.runtime_union_members(type_) is not None:
            self._target_error(
                node,
                'a union-typed result',
            )
        if isinstance(type_, ty.ArrayType):
            if type_.length is None:
                # Runtime-length results are arena-backed descriptors.
                return 'int64'
            self._target_error(
                node,
                'array return values require an exact compile-time length',
            )
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

    @staticmethod
    def _zero_initialized_scalar_global(item: hir.AST) -> bool:
        """A top-level scalar `let` whose literal initializer is zero (`let cursor:int64 = 0`, `let flag:bool = false`).

        Inert global storage is already zero, so no startup store is needed
        and the declaration does not by itself require module startup — the
        prelude's arena globals are of this kind, and without this every
        program would carry the startup wrapper just to store their zeros.
        """
        if not isinstance(item, hir.Declare):
            return False
        annotation = ty.strip_refinement(item.annotation or item.expr.type)
        if isinstance(item.expr, hir.Bool) and annotation == 'bool':
            return item.expr.value is False
        return (
            isinstance(item.expr, hir.Integer)
            and item.expr.value == 0
            and (
                (isinstance(annotation, str) and annotation in FIXED_INTEGER_WIDTHS)
                or isinstance(annotation, ty.IntegerLiteralType)
            )
        )

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
        if ty.runtime_union_members(annotation) is not None:
            # a tag-and-payload cell in static storage, addressed by this word
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
                members = ty.runtime_union_members(
                    item.annotation or item.expr.type
                )
                if members is not None and item.binding_id is not None:
                    self.union_cells[item.binding_id] = members
                enum = ty.enum_members(item.annotation or item.expr.type)
                if enum is not None and item.binding_id is not None:
                    self.enum_words[item.binding_id] = enum   # a word: the member index

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
        rettype = ty.strip_refinement(literal.rettype)   # `:>bigint<sign =? 1>` is an object result
        if (
            ty.optional_payload(rettype) is not None
            or ty.runtime_union_members(rettype) is not None
            or isinstance(rettype, ty.ObjectType)
            or (
                isinstance(rettype, ty.ArrayType)
                and rettype.length is not None
            )
        ):
            function.result_name = self._new_result_name()
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
            members = ty.runtime_union_members(param.type)
            if members is not None and param.binding_id is not None:
                self.union_cells[param.binding_id] = members
            enum = ty.enum_members(param.type)
            if enum is not None and param.binding_id is not None:
                self.enum_words[param.binding_id] = enum
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
            members = ty.runtime_union_members(param.type)
            if members is not None and param.binding_id is not None:
                self.union_cells[param.binding_id] = members
            enum = ty.enum_members(param.type)
            if enum is not None and param.binding_id is not None:
                self.enum_words[param.binding_id] = enum
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
        if isinstance(node, hir.Suppress):
            self._discover_node(node.item, scope, current_function)
            return
        if isinstance(node, hir.Assert):
            return  # proven during checking; nothing of it is lowered
        if isinstance(node, hir.Obligation):
            self._discover_node(node.value, scope, current_function, array_use=array_use)
            return
        if isinstance(node, hir.ExpressedIdentifier):
            binding = (
                self.binding_by_semantic_id.get(node.binding_id)
                if node.binding_id is not None
                else scope.resolve(node.name)
            )
            self.identifier_bindings[id(node)] = binding
            self.identifier_nodes[id(node)] = node
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
        if isinstance(node, hir.Place):
            self._discover_node(
                node.target,
                scope,
                current_function,
                array_use='representation',
            )
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
                            array_use=(
                                'index_read'
                                if isinstance(iterator.iterable.type, ty.ArrayType)
                                else None
                            ),
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
        if isinstance(node, hir.RangeMembership):
            self._discover_node(node.value, scope, current_function)
            self._discover_node(node.range, scope, current_function)
            return
        if isinstance(node, hir.ArrayLiteral):
            for item in node.items:
                self._discover_node(item, scope, current_function)
            return
        if isinstance(node, hir.Spread):
            # the copy loop reads the operand through its descriptor
            self._discover_node(node.value, scope, current_function, array_use='representation')
            return
        if isinstance(node, hir.ArrayLength):
            self._discover_node(
                node.array,
                scope,
                current_function,
                array_use='length',
            )
            return
        if isinstance(node, hir.ArrayMethod):
            self._discover_node(
                node.array,
                scope,
                current_function,
                array_use='grow',
            )
            return
        if isinstance(node, (hir.OrThrow, hir.ForwardingAccess)):
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, (hir.DictLookup, hir.DictContains)):
            self._discover_node(node.keys, scope, current_function, array_use='index_read')
            if isinstance(node, hir.DictLookup):
                self._discover_node(node.values, scope, current_function, array_use='index_read')
                if node.default is not None:
                    self._discover_node(node.default, scope, current_function)
            self._discover_node(node.key, scope, current_function)
            return
        if isinstance(node, hir.DictStore):
            self._discover_node(node.keys, scope, current_function, array_use='grow')
            if node.values is not None:
                self._discover_node(node.values, scope, current_function, array_use='grow')
            self._discover_node(node.key, scope, current_function)
            if node.value is not None:
                self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, hir.DictRemove):
            self._discover_node(node.keys, scope, current_function, array_use='grow')
            if node.values is not None:
                self._discover_node(node.values, scope, current_function, array_use='grow')
            if node.key is not None:
                self._discover_node(node.key, scope, current_function)
            if node.default is not None:
                self._discover_node(node.default, scope, current_function)
            return
        if isinstance(node, hir.DictEntries):
            self._discover_node(node.dictionary, scope, current_function)
            return
        if isinstance(node, hir.SetAlgebra):
            self._discover_node(node.left, scope, current_function)
            self._discover_node(node.right, scope, current_function)
            return
        if isinstance(node, hir.DictView):
            self._discover_node(node.dictionary, scope, current_function)
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
                array_use=(
                    'index_write'
                    if array_use == 'index_write'
                    else 'index_read'
                ),
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
        if isinstance(node, (hir.TypeValue, hir.GenericFunction)):
            return
        if isinstance(node, hir.FunctionCall):
            self.direct_calls.append((current_function, node))
            self.callee_nodes.add(id(node.func))
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
        """Plan lambda lifting for local functions that read enclosing locals.

        A capturing function gets each captured binding as a trailing hidden
        parameter, named as the body already spells it, and every direct call
        passes the caller's current value (which is itself a local or one of
        the caller's own lifted parameters). Writes to captured bindings and
        capturing functions used as values (closures that escape) are not
        supported yet and are rejected here.
        """
        needed: dict[int, list[_Binding]] = {}
        for function in self.functions:
            for use, binding in self.captures.get(id(function.literal), []):
                bindings = needed.setdefault(id(function), [])
                if binding not in bindings:
                    bindings.append(binding)
                self.lifted_types.setdefault(id(binding), self._lifted_param_type(binding, use))
        for function in self.functions:
            self._reject_captured_writes(function)
        # callers must be able to pass what their callees need
        changed = True
        while changed:
            changed = False
            for caller, call in self.direct_calls:
                callee = self._direct_call_function(call)
                if callee is None or id(callee) not in needed:
                    continue
                for binding in needed[id(callee)]:
                    if binding.owner_function is caller:
                        continue
                    if caller is None:
                        self._target_error(call, f'a call passing `{binding.name}` from a function into module-level code')
                    bindings = needed.setdefault(id(caller), [])
                    if binding not in bindings:
                        bindings.append(binding)
                        changed = True
        self.lifted = needed
        for function in self.functions:
            bindings = needed.get(id(function))
            if not bindings:
                continue
            names = ', '.join(f'`{binding.name}`' for binding in bindings)
            if function.literal.object_receiver:
                self._target_error(function.literal, f'an object method reading enclosing locals ({names})')
            for node_id, binding in self.identifier_bindings.items():
                if binding is not None and binding.function is function and node_id not in self.callee_nodes:
                    raise NotImplementedYet(Error(
                        srcfile=self.srcfile,
                        title='a capturing function used as a value',
                        message=f'`{function.logical_name}` reads {names} from an enclosing function, so it can only be called directly for now',
                        pointer_messages=[Pointer(span=self.identifier_nodes[node_id].loc, message='this use needs a closure record, which is not implemented yet')],
                        hint='call it directly, or pass the values it needs as parameters instead',
                    ))
            if function.logical_name == 'anon' and id(function.literal) not in self.callee_nodes:
                raise NotImplementedYet(Error(
                    srcfile=self.srcfile,
                    title='a capturing function used as a value',
                    message=f'this function reads {names} from an enclosing function, so it can only be called directly for now',
                    pointer_messages=[Pointer(span=function.literal.loc, message='closure records are not implemented yet')],
                    hint='bind it with `let` and call it by name, or pass the values it needs as parameters',
                ))

    def _lifted_param_type(self, binding: _Binding, use: hir.ExpressedIdentifier) -> ty.Type:
        if binding.semantic_id is not None and (
            binding.semantic_id in self.union_cells or binding.semantic_id in self.optional_payloads
        ):
            return 'int64'  # a cell pointer, whatever the use was narrowed to
        return self._lower_runtime_value_type(ty.strip_refinement(use.type))

    def _reject_captured_writes(self, function: _FunctionDef) -> None:
        """A captured binding is read-only inside the capturing function."""

        def root_identifier(node: hir.AST) -> hir.ExpressedIdentifier | None:
            while True:
                if isinstance(node, hir.MemberAccess):
                    node = node.value
                elif isinstance(node, hir.Index):
                    node = node.array
                elif isinstance(node, (hir.ValueCast, hir.RepresentationCast, hir.Transmute)):
                    node = node.expr
                elif isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
                    node = node.items[0]
                else:
                    break
            return node if isinstance(node, hir.ExpressedIdentifier) else None

        def written(node: hir.AST) -> hir.AST | None:
            if isinstance(node, hir.Assign):
                return node.target
            if isinstance(node, hir.MemberAssign):
                return node.target
            if isinstance(node, hir.IndexAssign):
                return node.target
            if isinstance(node, hir.Place):
                return node.target
            if isinstance(node, hir.FunctionCall) and isinstance(node.func, hir.ArrayMethod) and node.func.name != 'join':
                return node.func.array
            if isinstance(node, (hir.DictStore, hir.DictRemove)):
                return node.keys
            return None

        def walk(value: object) -> None:
            if isinstance(value, hir.FunctionLiteral):
                return  # nested functions plan their own captures
            if isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
                return
            if isinstance(value, hir.ObjectField):
                walk(value.value)
                return
            if not isinstance(value, hir.AST):
                return
            target = written(value)
            if target is not None:
                root = root_identifier(target)
                binding = self.identifier_bindings.get(id(root)) if root is not None else None
                if (
                    binding is not None
                    and binding.kind in {'param', 'value'}
                    and binding.owner_function is not None
                    and binding.owner_function is not function
                ):
                    self._target_error_at(
                        value,
                        f'writing to `{binding.name}`, which belongs to an enclosing function',
                        'a local function reads enclosing locals but cannot change them; keep shared mutable state in an object and pass it, or return the new value',
                    )
            for field_info in fields(value):
                if field_info.name in ('type', 'annotation'):
                    continue
                walk(getattr(value, field_info.name))

        walk(function.literal.body)

    def _target_error_at(self, node: hir.AST, message: str, hint: str) -> NoReturn:
        raise NotImplementedYet(Error(
            srcfile=self.srcfile,
            title='udewy target cannot lower this construct',
            pointer_messages=[Pointer(span=node.loc, message=message)],
            hint=hint,
        ))

    def _lifted_arguments(self, call: hir.FunctionCall) -> list[hir.AST]:
        """The caller's current values of everything the callee reads from enclosing scopes."""
        callee = self._direct_call_function(call)
        if callee is None:
            return []
        return [
            hir.ExpressedIdentifier(call.loc, self.lifted_types[id(binding)], binding.emitted_name or binding.name)
            for binding in self.lifted.get(id(callee), [])
        ]

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
            elif not param.required:
                normalized.extend([
                    self._default_placeholder(param.type, node.loc),
                    hir.Bool(node.loc, 'bool', False),
                ])
                source_positions.extend([None, None])
                optional_payloads.extend([None, None])
                continue
            else:
                raise ValueError(
                    f'INTERNAL ERROR: checked call is missing required parameter `{param.name}`'
                )
            normalized.append(argument)
            source_positions.append(source_position)
            optional_payloads.append(ty.optional_payload(param.type))
            if not param.required:
                normalized.append(hir.Bool(node.loc, 'bool', True))
                source_positions.append(None)
                optional_payloads.append(None)
        if len(pos_args) > len(function_type.pos_or_kw):
            if function_type.rest is None:
                raise ValueError('INTERNAL ERROR: rest arguments reached udewy lowering')
            for index in range(len(function_type.pos_or_kw), len(pos_args)):
                normalized.append(pos_args[index])
                source_positions.append(index)
                optional_payloads.append(None)
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
        if isinstance(node, hir.Suppress):
            return replace(
                node,
                item=self._require_node(self._transform_node(node.item)),
            )
        if isinstance(node, hir.Obligation):
            # proven by the bounds analysis before lowering: only the value remains
            return self._transform_node(node.value)
        if isinstance(node, hir.RationalConstant):
            self._target_error(node, 'a compile-time rational in this position')
        if isinstance(node, hir.ExpressedIdentifier):
            if self._is_compile_time_rational(node.type):
                self._target_error(node, 'a compile-time rational in this position')
            if self._is_range_valued(node.type):
                # Supported range uses were inlined during checking; anything
                # left needs a runtime range representation.
                self._target_error(node, 'a runtime range value')
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
        if isinstance(node, hir.Place):
            target = self._transform_node(node.target)
            if not isinstance(
                target,
                (hir.ExpressedIdentifier, hir.MemberAccess, hir.Index),
            ):
                raise TypeError('INTERNAL ERROR: place target was not preserved')
            return replace(node, target=target)
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
        if isinstance(node, hir.Spread):
            return replace(node, value=self._require_node(self._transform_node(node.value)))
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
        if isinstance(node, hir.OrThrow):
            return replace(
                node,
                value=self._require_node(self._transform_node(node.value)),
                propagated=self._require_node(self._transform_node(node.propagated)),
            )
        if isinstance(node, hir.ForwardingAccess):
            return replace(node, value=self._require_node(self._transform_node(node.value)))
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
        if isinstance(node, hir.GenericFunction):
            self._target_error(node, 'a generic function used as a value')
        if isinstance(node, hir.ModuleNamespace):
            self._target_error(node, 'using a module namespace as a runtime value')
        if isinstance(node, (hir.ArrayLength, hir.ArrayMethod)):
            return replace(
                node,
                array=self._require_node(self._transform_node(node.array)),
            )
        if isinstance(node, hir.DictLookup):
            return replace(
                node,
                keys=self._require_node(self._transform_node(node.keys)),
                values=self._require_node(self._transform_node(node.values)),
                key=self._require_node(self._transform_node(node.key)),
                default=(
                    self._require_node(self._transform_node(node.default))
                    if node.default is not None
                    else None
                ),
            )
        if isinstance(node, hir.DictContains):
            return replace(
                node,
                keys=self._require_node(self._transform_node(node.keys)),
                key=self._require_node(self._transform_node(node.key)),
            )
        if isinstance(node, hir.DictStore):
            return replace(
                node,
                keys=self._require_node(self._transform_node(node.keys)),
                values=self._require_node(self._transform_node(node.values)) if node.values is not None else None,
                key=self._require_node(self._transform_node(node.key)),
                value=self._require_node(self._transform_node(node.value)) if node.value is not None else None,
            )
        if isinstance(node, hir.DictRemove):
            return replace(
                node,
                keys=self._require_node(self._transform_node(node.keys)),
                values=self._require_node(self._transform_node(node.values)) if node.values is not None else None,
                key=self._require_node(self._transform_node(node.key)) if node.key is not None else None,
                default=self._require_node(self._transform_node(node.default)) if node.default is not None else None,
            )
        if isinstance(node, hir.DictEntries):
            return replace(node, dictionary=self._require_node(self._transform_node(node.dictionary)))
        if isinstance(node, hir.SetAlgebra):
            return replace(
                node,
                left=self._require_node(self._transform_node(node.left)),
                right=self._require_node(self._transform_node(node.right)),
            )
        if isinstance(node, hir.DictView):
            return replace(node, dictionary=self._require_node(self._transform_node(node.dictionary)))
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
                # a lambda-lifted callee also receives the enclosing values it reads
                pos_args=[*normalized, *self._lifted_arguments(node)],
                kw_args={},
                selected_method_index=None,
            )
            self._keyed_nodes_keepalive.append(transformed)
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
                union_slots: list[tuple[ty.TypeExpr, ...] | None] = []
                for param in source_function_type.pos_or_kw:
                    union_slots.append(ty.runtime_union_members(param.type))
                    if not param.required:
                        union_slots.append(None)
                self.call_union_args[id(transformed)] = union_slots
            called = self._direct_call_function(node)
            if called is not None and id(called) in self.string_result_needs_dest:
                # The transformed call loses resolvable identifier identity,
                # so record the destination-ABI target for the extract phase.
                self.string_result_call_targets[id(transformed)] = called
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
            if isinstance(node.expr, (hir.TypeValue, hir.GenericFunction)):
                return None
            if self._is_range_valued(node.annotation or node.expr.type):
                # Range bindings are compile-time values: every supported use
                # was resolved to the literal during checking, so the binding
                # needs no runtime storage.
                return None
            if self._is_compile_time_rational(node.annotation or node.expr.type):
                # Exact rational constants (unit scales) fold during checking.
                return None
            annotation = node.annotation
            if isinstance(node.annotation or node.expr.type, ty.QuantityType):
                # Dimensions are erased: the binding holds the number's word.
                annotation = self._lower_runtime_value_type(node.annotation or node.expr.type)
            return replace(
                node,
                annotation=annotation,
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
                and isinstance(node.type, (ty.QuantityType, ty.ObjectType))
            ):
                # Objects are one-word handles; quantities are their numbers.
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
        if isinstance(node, hir.RangeMembership):
            transformed_range = self._transform_node(node.range)
            if not isinstance(transformed_range, hir.Range):
                raise TypeError('INTERNAL ERROR: membership range was not preserved')
            return replace(
                node,
                value=self._require_node(self._transform_node(node.value)),
                range=transformed_range,
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
        return self._hoist_loop_allocations(lowered)

    def _hoist_loop_allocations(self, body: hir.AST) -> hir.AST:
        """Frame storage requested inside a loop is allocated once, at function entry.

        `__alloca__` grows the frame until the function returns, so a temporary
        object, union cell, or exact array allocated in a loop body would grow
        the stack every iteration (200 000 rational additions overflowed it).
        Every `let name = __alloca__(constant)` under a loop arm moves to the
        front of the body; the storage is then reused per iteration, which is
        sound because values are copied out of temporaries (value semantics)
        and nothing retains a frame address across iterations. Runtime-sized
        allocations stay where they are, and so does string storage: strings
        are immutable handles shared by reference (`pieces.push"{v}"` stores
        the descriptor's address), so one descriptor per loop would alias
        every iteration's string.
        """
        hoisted: list[hir.AST] = []

        def is_frame_allocation(item: hir.AST) -> bool:
            return (
                isinstance(item, hir.Declare)
                and isinstance(item.expr, hir.FunctionCall)
                and isinstance(item.expr.func, hir.ExpressedIdentifier)
                and item.expr.func.name in ('__alloca__', '__static_alloca__')
                and len(item.expr.pos_args) == 1
                and isinstance(item.expr.pos_args[0], hir.Integer)
                and not item.name.startswith('__dewy_string_')
            )

        def walk(node: hir.AST, in_loop: bool) -> hir.AST:
            if isinstance(node, hir.Block):
                items: list[hir.AST] = []
                for item in node.items:
                    if in_loop and is_frame_allocation(item):
                        hoisted.append(item)
                        continue
                    items.append(walk(item, in_loop))
                return replace(node, items=items)
            if isinstance(node, hir.Flow):
                arms = [
                    replace(arm, body=walk(arm.body, in_loop or isinstance(arm, hir.LoopArm)))
                    for arm in node.arms
                ]
                default = walk(node.default, in_loop) if node.default is not None else None
                return replace(node, arms=arms, default=default)
            if isinstance(node, hir.Suppress):
                return replace(node, item=walk(node.item, in_loop))
            return node

        rewritten = walk(body, False)
        if not hoisted:
            return body
        if isinstance(rewritten, hir.Block) and rewritten.scoped:
            return replace(rewritten, items=[*hoisted, *rewritten.items])
        return hir.Block(rewritten.loc, rewritten.type, [*hoisted, rewritten], True)

    def _lower_function_body_inner(self, node: hir.AST, rettype: ty.Type) -> hir.AST:
        """Make an implicit scalar function result explicit while lowering statements."""
        if rettype == ty.VOID_TYPE:
            # a `void` body may simply end: µDewy wants the return spelled out
            # (and a brace-less body such as `=> $expect …` is its statements, not a value)
            if isinstance(node, hir.Block) and not node.scoped:
                node = replace(node, scoped=True)
            lowered = self._lower_statement_body(node)
            if isinstance(lowered, hir.Block) and not (lowered.items and isinstance(lowered.items[-1], hir.Return)):
                return replace(lowered, items=[*lowered.items, hir.Return(node.loc, ty.BOTTOM_TYPE, None)])
            return lowered
        if self._contains_return(node):
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
                if self.current_array_result is not None:
                    items.extend(self._array_result_write(item))
                    continue
                if self.current_string_result is not None:
                    items.extend(self._string_result_write(item))
                    continue
                if self.current_union_result is not None:
                    items.extend(self._union_result_write(item))
                    continue
                if self.current_dynamic_array_result is not None:
                    items.extend(self._dynamic_array_result_write(item))
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
        elif self.current_array_result is not None:
            statements = self._array_result_write(node)
        elif self.current_string_result is not None:
            statements = self._string_result_write(node)
        elif self.current_union_result is not None:
            statements = self._union_result_write(node)
        elif self.current_dynamic_array_result is not None:
            statements = self._dynamic_array_result_write(node)
        else:
            prelude, value = self._extract_expression(node)
            statements = [*prelude, hir.Return(value.loc, ty.BOTTOM_TYPE, value)]
        return hir.Block(node.loc, ty.BOTTOM_TYPE, statements, True)

    @classmethod
    def _contains_nonlocal_exit(cls, node: hir.AST) -> bool:
        """Whether a body contains a break or continue targeting an outer loop."""
        if isinstance(node, (hir.Break, hir.Continue)):
            return node.loop_levels > 0
        if isinstance(node, hir.Suppress):
            return cls._contains_nonlocal_exit(node.item)
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
        if isinstance(node, hir.Suppress):
            return cls._contains_return(node.item)
        if isinstance(node, hir.Block):
            return any(cls._contains_return(item) for item in node.items)
        if isinstance(node, hir.Flow):
            return any(cls._contains_return(arm.body) for arm in node.arms) or (
                node.default is not None and cls._contains_return(node.default)
            )
        return False

    def _lower_statement(self, node: hir.AST) -> list[hir.AST]:
        """Return target statements, inserting expression-extraction preludes."""
        if isinstance(node, hir.Suppress):
            return self._lower_statement(node.item)
        if isinstance(node, (hir.ScopeMetatag, hir.Assert)):
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
            members = ty.runtime_union_members(declared_type)
            if members is not None:
                if self.lowering_module_startup:
                    self._target_error(
                        node, 'a module-level union binding'
                    )
                for member in members:
                    if not self._union_member_supported(member):
                        self._target_error(
                            node,
                            'a union member without a word-sized representation'
                            f' (`{type_to_dewy(member)}`)',
                        )
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
                    expr=self._union_cell_allocation(members, node.loc),
                )
                return [
                    declaration,
                    *self._union_prepare_trees(cell, members, node.loc),
                    *self._union_write(cell, node.expr, members, fresh=True),
                ]
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
            if (
                isinstance(declared_type, ty.ArrayType)
                and not self._array_expression_owns_fresh_storage(node.expr)
            ):
                copy_type = (
                    node.expr.type
                    if isinstance(node.expr.type, ty.ArrayType)
                    and node.expr.type.length is not None
                    else declared_type
                )
                copy_prelude, copied = self._clone_array_value(
                    node.expr,
                    copy_type,
                )
                return [
                    *copy_prelude,
                    replace(
                        node,
                        decltype='let',
                        annotation='int64',
                        expr=copied,
                    ),
                ]
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
                else 'int64'
                if ty.enum_members(node.expr.type) is not None   # an inferred enum binding is its tag word
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
            if isinstance(node.target.type, ty.ArrayType):
                return self._lower_array_assign(node)
            members = (
                self.union_cells.get(node.target.binding_id)
                if node.target.binding_id is not None
                else None
            )
            if members is not None:
                if node.op != '=':
                    self._target_error(
                        node, f'union compound assignment `{node.op}`'
                    )
                cell = replace(node.target, type='int64')
                prologue: list[hir.AST] = []
                binding = self.binding_by_semantic_id.get(node.target.binding_id)
                if (
                    self.lowering_module_startup
                    and binding is not None
                    and binding.owner_function is None
                    and node.target.binding_id not in self.union_globals_initialized
                ):
                    # A module-level union binding: its declaration became this
                    # startup assignment, so allocate the static cell (and the
                    # aggregate members' storage trees) here first.
                    prologue.append(
                        hir.Assign(
                            node.loc,
                            ty.VOID_TYPE,
                            cell,
                            '=',
                            self._union_cell_allocation(members, node.loc),
                        )
                    )
                    prologue.extend(self._union_prepare_trees(cell, members, node.loc))
                    self.union_globals_initialized.add(node.target.binding_id)
                return [*prologue, *self._union_write(cell, node.value, members)]
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
            assignment = replace(node, value=value)
            place_cell = (
                self.current_place_parameter_cells.get(node.target.binding_id)
                if node.target.binding_id is not None
                else None
            )
            if place_cell is None:
                return [*prelude, assignment]
            runtime_type = self._place_runtime_type(node.target.type, node)
            target = replace(node.target, type=runtime_type)
            return [
                *prelude,
                assignment,
                *self._value_store(target, place_cell, runtime_type, node.loc),
            ]
        if isinstance(node, hir.Return):
            if self.current_object_result is not None:
                if node.item is None:
                    self._target_error(node, 'object return without a value')
                return self._object_result_write(node.item)
            if self.current_array_result is not None:
                if node.item is None:
                    self._target_error(node, 'array return without a value')
                return self._array_result_write(node.item)
            if self.current_string_result is not None:
                if node.item is None:
                    self._target_error(node, 'string return without a value')
                return self._string_result_write(node.item)
            if self.current_union_result is not None:
                if node.item is None:
                    self._target_error(node, 'union return without a value')
                return self._union_result_write(node.item)
            if self.current_dynamic_array_result is not None:
                if node.item is None:
                    self._target_error(node, 'array return without a value')
                return self._dynamic_array_result_write(node.item)
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
        if prelude and isinstance(value, hir.Void):
            return prelude
        return [*prelude, value]

    # --- enums: unions of singletons as words -----------------------------

    def _enum_of(self, node: hir.AST) -> tuple[ty.TypeExpr, ...] | None:
        """The enum whose numbering a value's word uses.

        A binding's word carries its *declared* enum's tags even where the
        static type has been narrowed to fewer members (`'B' | 'C'` after an
        arm ruled out `'A'`), so the registered enum wins over the static type.
        """
        if isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
            registered = self.enum_words.get(node.binding_id)
            if registered is not None:
                return registered
        return ty.enum_members(node.type)

    @staticmethod
    def _enum_literal_of(type_: ty.Type, members: tuple[ty.TypeExpr, ...]) -> hir.AST | None:
        """A singleton type as its literal node, when it is one member of the enum."""
        stripped = ty.strip_refinement(type_)
        if isinstance(stripped, ty.StringLiteralType) and stripped in members:
            return hir.String(Span(0, 0), stripped, stripped.value)
        if isinstance(stripped, ty.IntegerLiteralType) and stripped in members:
            return hir.Integer(Span(0, 0), stripped, '0d', stripped.value)
        return None

    def _enum_word_of(self, value: hir.AST, members: tuple[ty.TypeExpr, ...]) -> tuple[list[hir.AST], hir.AST]:
        """``value`` as the tag word of the enum ``members``.

        A singleton is its member's index; a value of the same enum is the
        word itself; a narrower enum's word is remapped member by member.
        """
        while isinstance(value, (hir.RepresentationCast, hir.ValueCast)) and ty.enum_members(value.type) is not None:
            value = value.expr
        loc = value.loc
        stripped = ty.strip_refinement(value.type)
        index = ty.enum_member_index(members, stripped) if isinstance(stripped, (ty.StringLiteralType, ty.IntegerLiteralType)) else None
        if index is not None:
            return [], self._int64_literal(loc, index)
        source = self._enum_of(value)
        if source is None:
            self._target_error(value, 'a value that is not a member of the enum it is stored into')
        if isinstance(value, hir.ExpressedIdentifier) and value.binding_id in self.enum_words:
            prelude, word = [], replace(value, type='int64')
        else:
            prelude, word = self._extract_expression(value)
        if source == members:
            return prelude, word
        # remap: a narrower enum's tag `i` is the wider enum's tag of the same member
        held = hir.ExpressedIdentifier(loc, 'int64', self._new_optional_name('enum'))
        prelude = [*prelude, hir.Declare(loc, ty.VOID_TYPE, 'let', held.name, 'int64', word)]
        mapping = [(i, ty.enum_member_index(members, member)) for i, member in enumerate(source)]
        if any(target is None for _, target in mapping):
            self._target_error(value, 'a value that is not a member of the enum it is stored into')
        arms = [
            hir.IfArm(loc, 'int64', self._typed_equality(held, self._int64_literal(loc, i), 'int64', loc), self._int64_literal(loc, target))
            for i, target in mapping[:-1]
        ]
        flow = hir.Flow(loc, 'int64', arms, self._int64_literal(loc, mapping[-1][1]))
        flow_prelude, result = self._extract_expression(flow)
        return [*prelude, *flow_prelude], result

    def _enum_text_of(self, value: hir.AST, members: tuple[ty.TypeExpr, ...]) -> tuple[list[hir.AST], hir.AST]:
        """An enum word as the text of its member (a select over the literals)."""
        loc = value.loc
        literal = self._enum_literal_of(value.type, members)
        if literal is not None:
            return self._extract_expression(literal)
        prelude, word = self._enum_word_of(value, members)
        held = hir.ExpressedIdentifier(loc, 'int64', self._new_optional_name('enum'))
        prelude = [*prelude, hir.Declare(loc, ty.VOID_TYPE, 'let', held.name, 'int64', word)]
        def text(member: ty.TypeExpr) -> hir.AST:
            if isinstance(member, ty.StringLiteralType):
                return hir.String(loc, member, member.value)
            assert isinstance(member, ty.IntegerLiteralType)
            return hir.String(loc, ty.StringLiteralType(str(member.value)), str(member.value))
        arms = [
            hir.IfArm(loc, ty.StringType(), self._typed_equality(held, self._int64_literal(loc, i), 'int64', loc), text(member))
            for i, member in enumerate(members[:-1])
        ]
        flow = hir.Flow(loc, ty.StringType(), arms, text(members[-1]))
        flow_prelude, result = self._extract_expression(flow)
        return [*prelude, *flow_prelude], result

    def _extract_enum_type_test(self, node: hir.TypeTest) -> tuple[list[hir.AST], hir.AST] | None:
        """`c is? 'A'` on an enum word: a comparison of the word with the member's tag."""
        members = self._enum_of(node.value)
        if members is None:
            return None
        system = ty.TypeSystem()
        matching = [index for index, member in enumerate(members) if system.is_subtype(member, node.test_type) != node.negated]
        if len(matching) == len(members):
            return [], hir.Bool(node.loc, 'bool', True)
        if not matching:
            return [], hir.Bool(node.loc, 'bool', False)
        prelude, word = self._enum_word_of(node.value, members)
        test: hir.AST | None = None
        for index in matching:
            comparison = self._typed_equality(word, self._int64_literal(node.loc, index), 'int64', node.loc)
            test = comparison if test is None else hir.ShortCircuit(node.loc, 'bool', 'or', test, comparison)
        assert test is not None
        return prelude, test

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
            enum = self.enum_words.get(node.binding_id)
            if enum is not None:
                word = replace(node, type='int64')
                literal = self._enum_literal_of(node.type, enum)
                if literal is not None:
                    # narrowed to one member: the value is that literal
                    return self._extract_expression(literal)
                return [], word
            payload = self.optional_payloads.get(node.binding_id)
            if payload is not None:
                cell = replace(node, type='int64')
                if ty.optional_payload(node.type) is not None:
                    return [], cell
                return [], self._optional_load_payload(cell, payload, node.loc)
            members = self.union_cells.get(node.binding_id)
            if members is not None:
                cell = replace(node, type='int64')
                if isinstance(node.type, ty.TypeOr):
                    # Full or subset union view: tags are physical (the
                    # storage union's numbering), so the cell passes through
                    # and consumers consult the storage members.
                    return [], cell
                # Fully narrowed: load the payload as the matching member.
                system = ty.TypeSystem()
                member = next(
                    (m for m in members if system.is_subtype(node.type, m)),
                    None,
                )
                if member is None and node.type == 'int64':
                    # not a member: the lowering's own retyping (`replace(node,
                    # type='int64')`) of a `0 | [...]` cell — the cell address
                    return [], cell
                if member is None or member == 'undefined':
                    self._target_error(node, 'a union payload read of this type')
                loaded = self._optional_load_payload(cell, member, node.loc)
                if self._union_member_kind(member) == 'word':
                    return [], loaded
                # An aggregate member's pointer is bound to a temporary so the
                # copies that re-walk their source expression (an array field
                # clone) see a plain word, not the cell again.
                pointer = hir.ExpressedIdentifier(node.loc, 'int64', self._new_optional_name('member'))
                return [hir.Declare(node.loc, ty.VOID_TYPE, 'let', pointer.name, 'int64', loaded)], pointer
        if isinstance(node, hir.ObjectLiteral):
            return self._extract_object_literal(node)
        if isinstance(node, hir.MemberAccess):
            return self._extract_member_access(node)
        if isinstance(node, hir.Undefined):
            self._target_error(node, '`undefined` value without an optional context')
        if isinstance(node, hir.ErrorValue):
            # a unit-like error is its tag; the payload word is zero
            return [], hir.Integer(node.loc, 'int64', t0.base10, 0)
        if isinstance(node, hir.OrThrow):
            return self._extract_or_throw(node)
        if isinstance(node, hir.ForwardingAccess):
            return self._extract_forwarding_access(node)
        if isinstance(node, hir.TypeTest):
            enum_test = self._extract_enum_type_test(node)
            if enum_test is not None:
                return enum_test
            # Union operands test tags at runtime; fully narrowed operands
            # fold statically below. A union-typed identifier uses its
            # storage members, whose indexes stay physical even when the
            # static type is a narrowed subset union.
            members = ty.runtime_union_members(node.value.type)
            if (
                isinstance(node.value.type, ty.TypeOr)
                and isinstance(node.value, hir.ExpressedIdentifier)
                and node.value.binding_id is not None
            ):
                stored = self.union_cells.get(node.value.binding_id)
                if stored is not None:
                    members = stored
            if isinstance(node.value, hir.MemberAccess) and isinstance(node.value.value.type, ty.ObjectType):
                # a union field: its storage members are the declared field
                # type's, whatever the route has been narrowed to
                declared = node.value.value.type.field(node.value.name)
                stored = self._field_union_members(declared.type) if declared is not None else None
                if stored is not None:
                    members = stored
            if members is not None:
                union_prelude, union_value = self._extract_expression(node.value)
                system = ty.TypeSystem()
                matching = [
                    index
                    for index, member in enumerate(members)
                    if system.is_subtype(member, node.test_type) != node.negated
                ]
                if len(matching) == len(members):
                    return union_prelude, hir.Bool(node.loc, 'bool', True)
                if not matching:
                    return union_prelude, hir.Bool(node.loc, 'bool', False)
                cell = (
                    replace(union_value, type='int64')
                    if isinstance(union_value, hir.ExpressedIdentifier)
                    else union_value
                )
                tag = self._optional_tag(cell, node.loc)
                test: hir.AST | None = None
                for index in matching:
                    comparison = self._typed_equality(
                        tag,
                        self._uint8_literal(node.loc, index),
                        'uint8',
                        node.loc,
                    )
                    test = (
                        comparison
                        if test is None
                        else hir.ShortCircuit(
                            node.loc, 'bool', 'or', test, comparison
                        )
                    )
                assert test is not None
                return union_prelude, test
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
            union_members = ty.runtime_union_members(node.type)
            if union_members is not None:
                # a union-valued flow (`if c 'A' else 'C'`, a match over an
                # enum of string singletons): the arms tag a fresh cell
                cell = hir.ExpressedIdentifier(node.loc, 'int64', self._new_optional_name('flow_union'))
                prelude: list[hir.AST] = [
                    hir.Declare(node.loc, ty.VOID_TYPE, 'let', cell.name, 'int64', self._union_cell_allocation(union_members, node.loc)),
                    *self._union_prepare_trees(cell, union_members, node.loc),
                ]
                flow_prelude, flow = self._lower_union_flow(node, cell, union_members)
                return [*prelude, *flow_prelude, flow], replace(cell, type=node.type)
            target = self._new_flow_temp(node)
            declaration = hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64' if isinstance(node.type, ty.ArrayType) or ty.enum_members(node.type) is not None else node.type,
                self._placeholder(node),
            )
            flow_prelude, flow = self._lower_flow(node, target=target)
            return [declaration, *flow_prelude, flow], target
        if isinstance(node, hir.ShortCircuit):
            return self._extract_expression(self._short_circuit_flow(node))
        if isinstance(node, hir.RangeMembership):
            return self._extract_range_membership(node)
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
            return self._materialize_interpolated_string(node)
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
        if isinstance(node, hir.DictLookup):
            return self._extract_dict_lookup(node)
        if isinstance(node, hir.DictContains):
            return self._extract_dict_contains(node)
        if isinstance(node, hir.DictStore):
            return self._extract_dict_store(node)
        if isinstance(node, hir.DictRemove):
            return self._extract_dict_remove(node)
        if isinstance(node, hir.DictEntries):
            return self._extract_dict_entries(node)
        if isinstance(node, hir.SetAlgebra):
            return self._extract_set_algebra(node)
        if isinstance(node, hir.DictView):
            return self._extract_dict_view(node)
        if isinstance(node, hir.FunctionCall):
            if isinstance(node.func, hir.ArrayMethod):
                return self._extract_array_method_call(node)
            if self._is_object_method_func(node.func):
                return self._extract_method_call(node)
            if self._is_fixed_width_shift(node):
                return self._extract_fixed_width_shift(node)
            prelude: list[hir.AST] = []
            func_prelude, func = self._extract_expression(node.func)
            prelude.extend(func_prelude)
            function_type = (
                node.func.type
                if isinstance(node.func.type, ty.FunctionType)
                else None
            )
            optional_arguments = self.call_optional_args.get(id(node), [])
            union_arguments = self.call_union_args.get(id(node), [])
            pos_args: list[hir.AST] = []
            place_postlude: list[hir.AST] = []
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
                if isinstance(arg, hir.Place):
                    arg_prelude, lowered_arg, arg_postlude = (
                        self._materialize_place_argument(arg)
                    )
                    place_postlude.extend(arg_postlude)
                elif boundary is not None and boundary.safe:
                    arg_prelude, lowered_arg = self._materialize_array_call_argument(
                        arg,
                        boundary,
                    )
                elif (
                    boundary is not None
                    and boundary.parameter is not None
                    and isinstance(boundary.parameter.type, ty.ArrayType)
                ):
                    copy_type = boundary.parameter.type
                    arg_prelude, lowered_arg = self._independent_array_value(
                        arg,
                        copy_type,
                    )
                elif payload is not None:
                    arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
                elif (
                    union_arguments[index]
                    if index < len(union_arguments)
                    else ty.runtime_union_members(arg.type)
                ) is not None:
                    arg_members = (
                        union_arguments[index]
                        if index < len(union_arguments)
                        else ty.runtime_union_members(arg.type)
                    )
                    arg_prelude, lowered_arg = self._materialize_union(
                        arg,
                        arg_members,
                    )
                elif isinstance(arg.type, ty.ObjectType) or isinstance(expected_type, ty.ObjectType):
                    arg_prelude, lowered_arg = self._lower_object_argument(node, arg)
                else:
                    arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                pos_args.append(lowered_arg)
            kw_args: dict[str, hir.AST] = {}
            optional_kwargs = self.call_optional_kwargs.get(id(node), {})
            for name, arg in node.kw_args.items():
                payload = optional_kwargs.get(name)
                boundary = self.array_call_boundary_analyses.get((id(node), name))
                if isinstance(arg, hir.Place):
                    arg_prelude, lowered_arg, arg_postlude = (
                        self._materialize_place_argument(arg)
                    )
                    place_postlude.extend(arg_postlude)
                elif boundary is not None and boundary.safe:
                    arg_prelude, lowered_arg = self._materialize_array_call_argument(
                        arg,
                        boundary,
                    )
                elif (
                    boundary is not None
                    and boundary.parameter is not None
                    and isinstance(boundary.parameter.type, ty.ArrayType)
                ):
                    copy_type = boundary.parameter.type
                    arg_prelude, lowered_arg = self._independent_array_value(
                        arg,
                        copy_type,
                    )
                elif payload is not None:
                    arg_prelude, lowered_arg = self._materialize_optional(arg, payload)
                elif ty.runtime_union_members(arg.type) is not None:
                    arg_prelude, lowered_arg = self._materialize_union(
                        arg,
                        ty.runtime_union_members(arg.type),
                    )
                elif isinstance(arg.type, ty.ObjectType):
                    arg_prelude, lowered_arg = self._lower_object_argument(node, arg)
                else:
                    arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                kw_args[name] = lowered_arg
            if isinstance(node.type, ty.ObjectType):
                call_prelude, result = self._finish_object_call(
                    node,
                    func,
                    pos_args,
                    kw_args,
                    prelude,
                )
                return [*call_prelude, *place_postlude], result
            if isinstance(node.type, ty.ArrayType) and node.type.length is not None:
                call_prelude, result = self._finish_array_call(
                    node,
                    func,
                    pos_args,
                    kw_args,
                    prelude,
                )
                return [*call_prelude, *place_postlude], result
            if self._is_string_valued(node.type):
                called = self.string_result_call_targets.get(id(node))
                if called is not None:
                    call_prelude, result = self._finish_string_call(
                        node,
                        func,
                        pos_args,
                        kw_args,
                        prelude,
                        called,
                    )
                    return [*call_prelude, *place_postlude], result
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
                return [*prelude, *place_postlude], replace(result, type=node.type)
            result_members = ty.runtime_union_members(node.type)
            if result_members is not None:
                forwarded = self.union_result_destinations.pop(id(node), None)
                if forwarded is not None:
                    result = replace(forwarded, type='int64')
                else:
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
                            self._union_cell_allocation(result_members, node.loc),
                        )
                    )
                    prelude.extend(
                        self._union_prepare_trees(result, result_members, node.loc)
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
                return [*prelude, *place_postlude], replace(result, type=node.type)
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
            return self._finish_scalar_call_place_writebacks(
                call,
                prelude,
                place_postlude,
            )
        if isinstance(node, (hir.ValueCast, hir.Transmute)):
            prelude, expr = self._extract_expression(node.expr)
            return prelude, replace(node, expr=expr)
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
            prelude, item = self._extract_expression(node.items[0])
            return prelude, replace(node, items=[item])
        if isinstance(node, hir.Block) and not node.scoped and len(node.items) > 1:
            # statements followed by a value (a match's hidden scrutinee
            # before its flow): the statements run first, the value is the
            # last item
            prelude: list[hir.AST] = []
            for item in node.items[:-1]:
                prelude.extend(self._lower_statement(item))
            value_prelude, value = self._extract_expression(node.items[-1])
            return [*prelude, *value_prelude], value
        return [], node






















    @staticmethod
    def _copy_source_expression(node: hir.AST) -> hir.AST:
        """Discard wrappers that do not themselves create runtime storage."""

        while True:
            if isinstance(node, hir.ValueCast):
                node = node.expr
                continue
            if isinstance(node, hir.Block) and not node.scoped and len(node.items) == 1:
                node = node.items[0]
                continue
            return node

    def _array_expression_owns_fresh_storage(self, node: hir.AST) -> bool:
        node = self._copy_source_expression(node)
        return isinstance(node, (hir.ArrayLiteral, hir.FunctionCall)) or (
            isinstance(node, hir.RepresentationCast)
            and isinstance(node.type, ty.ArrayType)
        )





























    def _new_default_name(self, role: str) -> str:
        while True:
            name = f'__dewy_default_{role}_{self.next_default_temp}'
            self.next_default_temp += 1
            if name not in self.source_names:
                self.source_names.add(name)
                return name


    def _new_result_name(self) -> str:
        while True:
            name = f'__dewy_result_{self.next_result_temp}'
            self.next_result_temp += 1
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
            '__floordiv__',
            '__mod__',
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














    def _value_load(self, address: hir.AST, type_: ty.Type, loc: Span) -> hir.AST:
        if isinstance(type_, ty.ObjectType):
            return replace(address, type='int64')
        if self._field_union_members(type_) is not None:
            return replace(address, type='int64')  # a union value is its cell
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
        if self._is_handle_type(type_) or ty.is_user_nominal(type_):
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
        members = self._field_union_members(type_)
        if members is not None:
            return self._union_write(address, value, members, prepared=False)
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




























    def _result_destination_identifier(
        self,
        dest: hir.AST,
        result_type: ty.ArrayType | ty.ObjectType,
        loc: Span,
        *,
        object_result: bool,
    ) -> tuple[list[hir.AST], hir.ExpressedIdentifier]:
        """Give a nested prepared destination a stable name for call forwarding."""

        if isinstance(dest, hir.ExpressedIdentifier):
            return [], replace(dest, type=result_type)
        target = (
            self._new_object_temp(loc)
            if object_result
            else self._new_array_temp(hir.Void(loc, result_type))
        )
        return [
            hir.Declare(
                loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                'int64',
                replace(dest, type='int64'),
            )
        ], replace(target, type=result_type)

























    @staticmethod
    def _int64_literal(loc: Span, value: int) -> hir.Integer:
        return hir.Integer(loc, 'int64', t0.base10, value)








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


def lower_for_udewy(root: hir.AST, srcfile: SrcFile, *, entry_name: str = 'main') -> LoweredProgram:
    """Legalize checked HIR function constructs for udewy source emission."""
    if not isinstance(root, hir.Block):
        raise TypeError(f'expected Block, got {type(root).__name__}')
    return _Lowerer(root, srcfile, entry_name).lower()
