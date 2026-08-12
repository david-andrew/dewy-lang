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
  structured loops.

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
    function: _FunctionDef | None = None


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
        self.next_loop_signal = 1
        self.loop_signal_levels: hir.ExpressedIdentifier | None = None
        self.loop_signal_kind: hir.ExpressedIdentifier | None = None
        self.lower_loop_depth = 0
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
        self._check_captures()
        self.needs_startup = any(
            not (
                isinstance(item, hir.Declare)
                and (binding := self.declare_bindings.get(id(item))) is not None
                and binding.kind in {'function', 'overload'}
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
                globals_.append(self._global_storage(transformed))
                assignment = hir.Assign(
                    transformed.loc,
                    ty.VOID_TYPE,
                    hir.ExpressedIdentifier(
                        transformed.loc,
                        transformed.expr.type,
                        transformed.name,
                    ),
                    '=',
                    transformed.expr,
                )
                startup_sources.append(assignment)
            else:
                startup_sources.append(transformed)
        startup_items: list[hir.AST] = []
        if startup_sources:
            startup = self._lower_function_body(
                hir.Block(
                    self.root.loc,
                    ty.VOID_TYPE,
                    startup_sources,
                    True,
                ),
                ty.VOID_TYPE,
            )
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
        rettype = self._target_scalar_type(literal.rettype, literal)
        function_type = literal.type
        if isinstance(function_type, ty.FunctionType):
            function_type = replace(function_type, ret=rettype)
        return LoweredFunction(
            function.symbol,
            replace(
                literal,
                type=function_type,
                pos_or_kw_args=[
                    self._transform_param(param)
                    for param in literal.pos_or_kw_args
                ],
                kw_only_args=[
                    self._transform_param(param)
                    for param in literal.kw_only_args
                ],
                rest_args=(
                    self._transform_param(literal.rest_args)
                    if literal.rest_args is not None
                    else None
                ),
                rettype=rettype,
                body=self._lower_function_body(
                    self._require_node(self._transform_node(literal.body)),
                    literal.rettype,
                ),
            ),
        )

    def _target_scalar_type(self, type_: ty.Type, node: hir.AST) -> ty.Type:
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
                self._discover_node(
                    declare.expr,
                    scope,
                    current_function,
                    suggested_name=declare.name if binding.kind == 'overload' else None,
                    overload_member=binding.kind == 'overload',
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
        for param in literal.kw_only_args:
            self._new_binding(
                function_scope,
                param.name,
                'param',
                function,
                None,
                param.binding_id,
            )
        if literal.rest_args is not None:
            self._new_binding(
                function_scope,
                literal.rest_args.name,
                'param',
                function,
                None,
                literal.rest_args.binding_id,
            )
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
    ) -> None:
        """Resolve names and recursively collect callable constructs in ``node``."""
        if isinstance(node, hir.ExpressedIdentifier):
            binding = (
                self.binding_by_semantic_id.get(node.binding_id)
                if node.binding_id is not None
                else scope.resolve(node.name)
            )
            self.identifier_bindings[id(node)] = binding
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
                self._discover_node(arm.condition, scope, current_function)
                self._discover_node(arm.body, scope, current_function)
            if node.default is not None:
                self._discover_node(node.default, scope, current_function)
            return
        if isinstance(node, hir.ShortCircuit):
            self._discover_node(node.left, scope, current_function)
            self._discover_node(node.right, scope, current_function)
            return
        if isinstance(node, hir.FunctionCall):
            self._discover_node(node.func, scope, current_function)
            for arg in node.pos_args:
                self._discover_node(arg, scope, current_function)
            for arg in node.kw_args.values():
                self._discover_node(arg, scope, current_function)
            return
        if isinstance(node, hir.Assign):
            self._discover_node(node.target, scope, current_function)
            self._discover_node(node.value, scope, current_function)
            return
        if isinstance(node, (hir.ValueCast, hir.Transmute)):
            self._discover_node(node.expr, scope, current_function)
            return
        if isinstance(node, hir.TypeBlock):
            for item in node.items:
                self._discover_node(item, scope, current_function)
            return
        if isinstance(node, hir.Range):
            if node.step_pair is not None:
                for item in node.step_pair:
                    self._discover_node(item, scope, current_function)
            if node.left is not None:
                self._discover_node(node.left, scope, current_function)
            if node.right is not None:
                self._discover_node(node.right, scope, current_function)

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
            return replace(param, value=self._require_node(self._transform_node(param.value)))
        return param

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
                return replace(node, name=binding.function.symbol)
            if binding.kind == 'overload':
                self._target_error(node, 'runtime multifunction values are not supported by udewy')
            return node
        if isinstance(node, hir.FunctionLiteral):
            function = self.function_by_literal[id(node)]
            return hir.ExpressedIdentifier(node.loc, node.type, function.symbol)
        if isinstance(node, hir.OverloadedFunction):
            self._target_error(node, 'runtime multifunction values are not supported by udewy')
        if isinstance(node, hir.FunctionCall):
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
            else:
                func = self._require_node(self._transform_node(node.func))
            return replace(
                node,
                func=func,
                pos_args=[
                    self._require_node(self._transform_node(arg))
                    for arg in node.pos_args
                ],
                kw_args={
                    name: self._require_node(self._transform_node(arg))
                    for name, arg in node.kw_args.items()
                },
                selected_method_index=None,
            )
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
        if isinstance(node, hir.Assign):
            return replace(
                node,
                target=self._require_identifier(self._transform_node(node.target)),
                value=self._require_node(self._transform_node(node.value)),
            )
        if isinstance(node, (hir.ValueCast, hir.Transmute)):
            return replace(
                node,
                expr=self._require_node(self._transform_node(node.expr)),
            )
        if isinstance(node, hir.TypeBlock):
            return replace(
                node,
                items=[
                    self._require_node(self._transform_node(item))
                    for item in node.items
                ],
            )
        if isinstance(node, hir.Range):
            return replace(
                node,
                step_pair=(
                    tuple(
                        self._require_node(self._transform_node(item))
                        for item in node.step_pair
                    )
                    if node.step_pair is not None
                    else None
                ),
                left=(
                    self._require_node(self._transform_node(node.left))
                    if node.left is not None
                    else None
                ),
                right=(
                    self._require_node(self._transform_node(node.right))
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
                prelude, value = self._extract_expression(item)
                items.extend(prelude)
                items.append(hir.Return(value.loc, ty.BOTTOM_TYPE, value))
            return replace(node, type=ty.BOTTOM_TYPE, items=items)
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
            return [self._lower_statement_body(node)]
        if isinstance(node, hir.Flow):
            is_loop = any(isinstance(arm, hir.LoopArm) for arm in node.arms)
            prelude, flow = self._lower_flow(node)
            statements: list[hir.AST] = [*prelude, flow]
            if (
                is_loop
                and self.lower_loop_depth > 0
                and self.loop_signal_levels is not None
            ):
                statements.extend(self._loop_signal_checkpoint(node.loc))
            return statements
        if isinstance(node, hir.Declare):
            prelude, expr = self._extract_expression(node.expr)
            return [*prelude, replace(node, expr=expr)]
        if isinstance(node, hir.Assign):
            prelude, value = self._extract_expression(node.value)
            return [*prelude, replace(node, value=value)]
        if isinstance(node, hir.Return):
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
        if isinstance(node, hir.Flow):
            if node.type in (ty.VOID_TYPE, ty.BOTTOM_TYPE):
                self._target_error(node, 'statement-only flow used where a value is required')
            target = self._new_flow_temp(node)
            declaration = hir.Declare(
                node.loc,
                ty.VOID_TYPE,
                'let',
                target.name,
                node.type,
                self._placeholder(node),
            )
            flow_prelude, flow = self._lower_flow(node, target=target)
            return [declaration, *flow_prelude, flow], target
        if isinstance(node, hir.ShortCircuit):
            return self._extract_expression(self._short_circuit_flow(node))
        if isinstance(node, hir.FunctionCall):
            prelude: list[hir.AST] = []
            func_prelude, func = self._extract_expression(node.func)
            prelude.extend(func_prelude)
            pos_args: list[hir.AST] = []
            for arg in node.pos_args:
                arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                pos_args.append(lowered_arg)
            kw_args: dict[str, hir.AST] = {}
            for name, arg in node.kw_args.items():
                arg_prelude, lowered_arg = self._extract_expression(arg)
                prelude.extend(arg_prelude)
                kw_args[name] = lowered_arg
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

    def _prepare_condition(self, node: hir.AST) -> tuple[list[hir.AST], hir.AST]:
        """Preserve lazy boolean operators while lowering their operands."""
        if isinstance(node, hir.ShortCircuit):
            left_prelude, left = self._prepare_condition(node.left)
            right_prelude, right = self._prepare_condition(node.right)
            if right_prelude:
                self._target_error(
                    node.right,
                    'right short-circuit operand requiring extracted statements',
                )
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