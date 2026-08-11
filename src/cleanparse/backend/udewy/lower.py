"""Legalize checked HIR for targets with udewy's function model.

This module sits between semantic checking and source emission. It is not the
general HIR-to-MIR pass: it handles callable constructs that are valid Dewy HIR
but cannot be represented directly by udewy:

- udewy functions must be top-level, so non-capturing local functions are
  collected, assigned module-level symbols, and hoisted;
- udewy has no runtime overload sets, so statically selected overload calls are
  rewritten to their concrete function alternatives;
- udewy has no closures, so references to enclosing function values are
  diagnosed before emission.

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
from typing import NoReturn

from ...reporting import Error, Pointer, SrcFile
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
    and inline alternatives. ``remaining_items`` contains non-callable
    top-level HIR that this pass deliberately leaves for the backend to handle.
    """

    functions: list[LoweredFunction]
    remaining_items: list[hir.AST]


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
        self.identifier_bindings: dict[int, _Binding | None] = {}
        self.captures: dict[int, list[tuple[hir.ExpressedIdentifier, _Binding]]] = defaultdict(list)

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
        self._allocate_symbols()

        lowered_functions = [
            LoweredFunction(
                function.symbol,
                replace(
                    function.literal,
                    pos_or_kw_args=[
                        self._transform_param(param)
                        for param in function.literal.pos_or_kw_args
                    ],
                    kw_only_args=[
                        self._transform_param(param)
                        for param in function.literal.kw_only_args
                    ],
                    rest_args=(
                        self._transform_param(function.literal.rest_args)
                        if function.literal.rest_args is not None
                        else None
                    ),
                    body=self._require_node(self._transform_node(function.literal.body)),
                ),
            )
            for function in sorted(self.functions, key=lambda item: item.order)
        ]

        remaining_items: list[hir.AST] = []
        for item in self.root.items:
            binding = self.declare_bindings.get(id(item))
            if binding is not None and binding.kind in {'function', 'overload'}:
                continue
            transformed = self._transform_node(item)
            if transformed is not None:
                remaining_items.append(transformed)
        return LoweredProgram(lowered_functions, remaining_items)

    def _new_binding(
        self,
        scope: _Scope,
        name: str,
        kind: str,
        owner_function: _FunctionDef | None,
        expr: hir.AST | None,
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

        Fully checked function literals are pre-bound before any item is
        visited. This preserves forward references, self-recursion, and mutual
        recursion. Other declarations remain source-order dependent.
        """
        if block.scoped and create_scope:
            scope = self._new_block_scope(
                scope,
                current_function,
                function_body=function_body,
            )

        for item in block.items:
            if isinstance(item, hir.Declare) and isinstance(item.expr, hir.FunctionLiteral):
                binding = self._new_binding(
                    scope,
                    item.name,
                    'function',
                    current_function,
                    item.expr,
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
            if not isinstance(declare.expr, hir.FunctionLiteral):
                raise TypeError('INTERNAL ERROR: pre-bound declaration is not a function')
            function = self._new_function(
                declare.expr,
                declare.name,
                scope,
                overload_member=False,
            )
            binding.function = function
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
            self._new_binding(function_scope, param.name, 'param', function, None)
        for param in literal.kw_only_args:
            self._new_binding(function_scope, param.name, 'param', function, None)
        if literal.rest_args is not None:
            self._new_binding(
                function_scope,
                literal.rest_args.name,
                'param',
                function,
                None,
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
            binding = scope.resolve(node.name)
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
                alternatives = self._resolve_callable(node.func)
                if len(alternatives) != len(node.func.type.methods):
                    raise ValueError(
                        'INTERNAL ERROR: overload alternatives do not align with methods'
                    )
                selected = alternatives[node.selected_method_index]
                func: hir.AST = hir.ExpressedIdentifier(
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

    def _target_error(self, node: hir.AST, message: str) -> NoReturn:
        """Report a valid HIR callable construct unsupported by udewy."""
        raise NotImplementedYet(Error(
            srcfile=self.srcfile,
            title='udewy target cannot lower this callable',
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