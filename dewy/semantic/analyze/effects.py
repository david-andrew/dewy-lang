"""Recursive, transitive effect analysis for aggregate parameters.

Summarizes, for every concrete function parameter, how the function body may
act on the value bound to that parameter: reads, in-place mutation,
whole-value rebinding, and escapes. Each effect is keyed by a route of field
and index steps into the value, so consumers can distinguish `items[0] = x`
from `root.field[i].leaf = x`.

Effects propagate through statically resolved direct calls to a fixed point.
Under value semantics an ordinary argument only *reads* the caller's value —
the call boundary itself decides whether to copy or borrow using the callee's
own summary — so only `@` place arguments translate the callee's write and
escape effects back onto the caller's storage. Unresolved or indirect calls
are conservative: a place argument to an unknown callee is treated as read,
mutated, rebound, and escaped.

The first consumer is the udewy lowering pass, which uses these summaries to
decide when a value-semantic call boundary may borrow the caller's storage
instead of copying, replacing the array-specific boundary checks.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .. import hir, ty

INDEX_STEP = '[]'
"""Route step standing for any element of an array; field steps use the name."""

type Route = tuple[str, ...]
ROOT: Route = ()

MAX_ROUTE_DEPTH = 8
"""Routes deeper than this are truncated; a truncated route conservatively
covers everything at or below the truncation point."""


def _covered(routes: set[Route], route: Route) -> bool:
    """Whether ``route`` is already implied by a stored route.

    A stored route means "at or below this point", so any stored prefix of
    ``route`` (including ``route`` itself) covers it.
    """
    return any(route[: len(stored)] == stored for stored in routes)


def _add_route(routes: set[Route], route: Route) -> bool:
    """Add ``route``, keeping the set prefix-dominance normalized.

    Returns whether coverage grew. Stored extensions of the new route are
    dropped because the new, shorter route subsumes them.
    """
    route = route[:MAX_ROUTE_DEPTH]
    if _covered(routes, route):
        return False
    routes.difference_update({
        stored for stored in routes if stored[: len(route)] == route
    })
    routes.add(route)
    return True


@dataclass
class ParameterEffects:
    """What one function body may do to the value bound to one parameter.

    Every set holds routes into the parameter value. An entry covers the
    value at that route and everything below it. ``rebinds`` records
    whole-value replacement of the value at the route, which for the empty
    route is rebinding the parameter itself.
    """

    reads: set[Route] = field(default_factory=set)
    mutates: set[Route] = field(default_factory=set)
    rebinds: set[Route] = field(default_factory=set)
    escapes: set[Route] = field(default_factory=set)

    @property
    def writes(self) -> bool:
        return bool(self.mutates or self.rebinds)

    @property
    def read_only(self) -> bool:
        return not self.writes and not self.escapes

    def add_read(self, route: Route) -> bool:
        return _add_route(self.reads, route)

    def add_mutate(self, route: Route) -> bool:
        return _add_route(self.mutates, route)

    def add_rebind(self, route: Route) -> bool:
        return _add_route(self.rebinds, route)

    def add_escape(self, route: Route) -> bool:
        return _add_route(self.escapes, route)

    def add_opaque(self, route: Route) -> bool:
        """Assume every effect at or below ``route`` (unknown callee)."""
        changed = self.add_read(route)
        changed |= self.add_mutate(route)
        changed |= self.add_rebind(route)
        changed |= self.add_escape(route)
        return changed

    def merge_translated(self, other: ParameterEffects, prefix: Route) -> bool:
        """Fold ``other`` (a callee place parameter's effects) in at ``prefix``."""
        changed = False
        for route in other.reads:
            changed |= self.add_read(prefix + route)
        for route in other.mutates:
            changed |= self.add_mutate(prefix + route)
        for route in other.rebinds:
            changed |= self.add_rebind(prefix + route)
        for route in other.escapes:
            changed |= self.add_escape(prefix + route)
        return changed

    def copy(self) -> ParameterEffects:
        return ParameterEffects(
            set(self.reads),
            set(self.mutates),
            set(self.rebinds),
            set(self.escapes),
        )


@dataclass
class FunctionEffects:
    """Per-parameter effect summaries for one concrete function literal."""

    literal: hir.FunctionLiteral
    params: dict[int, ParameterEffects]

    def for_param(self, parameter: hir.Param) -> ParameterEffects | None:
        if parameter.binding_id is None:
            return None
        return self.params.get(parameter.binding_id)


@dataclass
class ProgramEffects:
    """Effect summaries for every function literal in a checked program."""

    by_literal: dict[int, FunctionEffects]
    by_param_binding: dict[int, ParameterEffects]

    def for_literal(self, literal: hir.FunctionLiteral) -> FunctionEffects | None:
        return self.by_literal.get(id(literal))

    def for_param_binding(self, binding_id: int) -> ParameterEffects | None:
        return self.by_param_binding.get(binding_id)


def _unwrap(node: hir.AST) -> hir.AST:
    """Skip transparent single-expression blocks."""
    while (
        isinstance(node, hir.Block)
        and not node.scoped
        and len(node.items) == 1
    ):
        node = node.items[0]
    return node


def _iter_values(value: object):
    if isinstance(value, hir.AST):
        yield value
    elif isinstance(value, hir.ObjectField):
        yield value.value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_values(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_values(item)


def _iter_children(node: hir.AST):
    for f in dataclasses.fields(node):
        yield from _iter_values(getattr(node, f.name))


def _literal_params(literal: hir.FunctionLiteral) -> list[hir.Param]:
    params = [*literal.pos_or_kw_args, *literal.kw_only_args]
    if literal.rest_args is not None:
        params.append(literal.rest_args)
    return params


class _EffectAnalyzer:
    def __init__(self, root: hir.AST):
        self.root = root
        self.literals: list[hir.FunctionLiteral] = []
        self.declares: dict[int, hir.Declare] = {}
        self.reassigned: set[int] = set()
        self.param_binding_ids: set[int] = set()
        self._collect(root)
        self.effects: dict[int, FunctionEffects] = {
            id(literal): FunctionEffects(
                literal,
                {
                    param.binding_id: ParameterEffects()
                    for param in _literal_params(literal)
                    if param.binding_id is not None
                },
            )
            for literal in self.literals
        }

    # ------------------------------------------------------------------
    # program structure collection

    def _collect(self, node: object) -> None:
        if isinstance(node, hir.FunctionLiteral):
            self.literals.append(node)
            for param in _literal_params(node):
                if param.binding_id is not None:
                    self.param_binding_ids.add(param.binding_id)
        elif isinstance(node, hir.Declare):
            if node.binding_id is not None:
                self.declares[node.binding_id] = node
        elif isinstance(node, hir.Assign):
            if node.target.binding_id is not None:
                self.reassigned.add(node.target.binding_id)
        if isinstance(node, hir.AST):
            for child in _iter_children(node):
                self._collect(child)

    # ------------------------------------------------------------------
    # direct-call resolution

    def _flatten_callable(
        self,
        node: hir.AST,
        seen: frozenset[int],
    ) -> list[hir.FunctionLiteral] | None:
        """Flatten a callable expression into dispatch-order literals.

        The order must match ``OverloadType.methods`` so that a call's
        ``selected_method_index`` picks the same concrete function the
        checker selected. Returns None when any part cannot be resolved
        statically.
        """
        node = _unwrap(node)
        if isinstance(node, hir.FunctionLiteral):
            return [node]
        if isinstance(node, hir.OverloadedFunction):
            flattened: list[hir.FunctionLiteral] = []
            for alternate in node.alternates:
                resolved = self._flatten_callable(alternate, seen)
                if resolved is None:
                    return None
                flattened.extend(resolved)
            return flattened
        if isinstance(node, hir.ExpressedIdentifier):
            binding_id = node.binding_id
            if binding_id is None or binding_id in seen:
                return None
            if binding_id in self.param_binding_ids:
                return None  # indirect call through a parameter
            if binding_id in self.reassigned:
                return None
            declaration = self.declares.get(binding_id)
            if declaration is None:
                return None
            return self._flatten_callable(
                declaration.expr,
                seen | {binding_id},
            )
        return None

    def _direct_targets(
        self,
        call: hir.FunctionCall,
    ) -> list[hir.FunctionLiteral] | None:
        targets = self._flatten_callable(call.func, frozenset())
        if targets is None:
            return None
        if call.selected_method_index is not None:
            if call.selected_method_index >= len(targets):
                return None
            return [targets[call.selected_method_index]]
        if len(targets) != 1:
            # A multi-target call without a recorded selection: merge every
            # alternative conservatively.
            return targets if targets else None
        return targets

    @staticmethod
    def _pair_arguments(
        call: hir.FunctionCall,
        literal: hir.FunctionLiteral,
    ) -> list[tuple[hir.AST, hir.Param | None]] | None:
        """Match call arguments to ``literal``'s parameters.

        Named arguments claim their parameter and remove it from the
        positional sequence; remaining positional arguments bind the still
        available positional-or-keyword parameters left to right. Returns
        None when the shape cannot be matched (the conservative path).
        """
        named = {
            param.name: param
            for param in [*literal.pos_or_kw_args, *literal.kw_only_args]
        }
        claimed = set(call.kw_args)
        positional = [
            param
            for param in literal.pos_or_kw_args
            if param.name not in claimed
        ]
        pairs: list[tuple[hir.AST, hir.Param | None]] = []
        for index, argument in enumerate(call.pos_args):
            if index < len(positional):
                pairs.append((argument, positional[index]))
            elif literal.rest_args is not None:
                pairs.append((argument, None))
            else:
                return None
        for name, argument in call.kw_args.items():
            parameter = named.get(name)
            if parameter is None:
                return None
            pairs.append((argument, parameter))
        return pairs

    # ------------------------------------------------------------------
    # per-function summarization

    def solve(self) -> ProgramEffects:
        changed = True
        while changed:
            changed = False
            for literal in self.literals:
                summary = self._summarize(literal)
                current = self.effects[id(literal)]
                if summary.params != current.params:
                    self.effects[id(literal)] = summary
                    changed = True
        by_param: dict[int, ParameterEffects] = {}
        for function_effects in self.effects.values():
            by_param.update(function_effects.params)
        return ProgramEffects(dict(self.effects), by_param)

    def _summarize(self, literal: hir.FunctionLiteral) -> FunctionEffects:
        params = {
            param.binding_id: ParameterEffects()
            for param in _literal_params(literal)
            if param.binding_id is not None
        }
        self._visit(literal.body, params)
        return FunctionEffects(literal, params)

    def _resolve_route(
        self,
        node: hir.AST,
        params: dict[int, ParameterEffects],
    ) -> tuple[int, Route, list[hir.AST]] | None:
        """Resolve a parameter-rooted access chain to (binding, route, inner).

        ``inner`` collects index expressions embedded in the chain, which the
        caller must still visit for their own parameter uses.
        """
        steps: list[str] = []
        inner: list[hir.AST] = []
        while True:
            node = _unwrap(node)
            if isinstance(node, hir.MemberAccess):
                steps.append(node.name)
                node = node.value
                continue
            if isinstance(node, hir.Index):
                steps.append(INDEX_STEP)
                inner.append(node.index)
                node = node.array
                continue
            if (
                isinstance(node, hir.ExpressedIdentifier)
                and node.binding_id in params
            ):
                return node.binding_id, tuple(reversed(steps)), inner
            return None

    def _visit(
        self,
        node: hir.AST | None,
        params: dict[int, ParameterEffects],
    ) -> None:
        if node is None or not params:
            return
        if isinstance(node, hir.FunctionCall):
            self._visit_call(node, params)
            return
        if isinstance(node, hir.IndexAssign):
            resolved = self._resolve_route(node.target.array, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_mutate(route + (INDEX_STEP,))
                for expr in inner:
                    self._visit(expr, params)
            else:
                self._visit(node.target.array, params)
            self._visit(node.target.index, params)
            self._visit(node.value, params)
            return
        if isinstance(node, hir.MemberAssign):
            resolved = self._resolve_route(node.target.value, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_mutate(route + (node.target.name,))
                for expr in inner:
                    self._visit(expr, params)
            else:
                self._visit(node.target.value, params)
            self._visit(node.value, params)
            return
        if isinstance(node, hir.Assign):
            if node.target.binding_id in params:
                params[node.target.binding_id].add_rebind(ROOT)
            self._visit(node.value, params)
            return
        if isinstance(node, hir.IteratorExpression):
            if node.target.binding_id in params:
                params[node.target.binding_id].add_rebind(ROOT)
            self._visit(node.iterable, params)
            return
        if isinstance(node, hir.MemberAccess) and isinstance(
            node.type, (ty.FunctionType, ty.OverloadType)
        ):
            # A function-valued member captures its receiver, so reading it
            # (or calling it, directly or later) may mutate sibling fields.
            # The member value is runtime data, so this stays conservative.
            resolved = self._resolve_route(node.value, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_opaque(route)
                for expr in inner:
                    self._visit(expr, params)
                return
            self._visit(node.value, params)
            return
        if isinstance(node, (hir.Index, hir.MemberAccess)):
            resolved = self._resolve_route(node, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_read(route)
                for expr in inner:
                    self._visit(expr, params)
                return
            for child in _iter_children(node):
                self._visit(child, params)
            return
        if isinstance(node, hir.ArrayLength):
            resolved = self._resolve_route(node.array, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_read(route)
                for expr in inner:
                    self._visit(expr, params)
                return
            self._visit(node.array, params)
            return
        if isinstance(node, hir.RepresentationCast):
            # Representation casts may produce views that borrow the source
            # storage (`string as array<uint8>` is copy-on-write over the
            # original bytes). Until the analysis models which casts alias,
            # a cast of a parameter route conservatively escapes it.
            resolved = self._resolve_route(node.expr, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_read(route)
                params[binding_id].add_escape(route)
                for expr in inner:
                    self._visit(expr, params)
                return
            self._visit(node.expr, params)
            return
        if isinstance(node, hir.ExpressedIdentifier):
            if node.binding_id in params:
                params[node.binding_id].add_read(ROOT)
            return
        if isinstance(node, hir.Place):
            # A place outside a call argument has no defined consumer yet;
            # assume the worst for its parameter root.
            resolved = self._resolve_route(node.target, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_opaque(route)
                for expr in inner:
                    self._visit(expr, params)
            return
        for child in _iter_children(node):
            self._visit(child, params)

    def _visit_call(
        self,
        call: hir.FunctionCall,
        params: dict[int, ParameterEffects],
    ) -> None:
        if isinstance(call.func, hir.ArrayMethod):
            # Growth methods mutate the receiver array in place.
            resolved = self._resolve_route(call.func.array, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                params[binding_id].add_mutate(route)
                for expr in inner:
                    self._visit(expr, params)
            else:
                self._visit(call.func.array, params)
            for argument in [*call.pos_args, *call.kw_args.values()]:
                self._visit(argument, params)
            return
        self._visit(call.func, params)
        targets = self._direct_targets(call)
        pairings: list[list[tuple[hir.AST, hir.Param | None]]] | None = None
        if targets is not None:
            resolved_pairs = [
                self._pair_arguments(call, target) for target in targets
            ]
            if all(pairs is not None for pairs in resolved_pairs):
                pairings = [pairs for pairs in resolved_pairs if pairs is not None]
        arguments = [*call.pos_args, *call.kw_args.values()]
        for argument in arguments:
            if isinstance(argument, hir.Place):
                self._visit_place_argument(argument, call, targets, pairings, params)
            else:
                resolved = self._resolve_route(argument, params)
                if resolved is not None:
                    binding_id, route, inner = resolved
                    # Value semantics: the boundary reads the argument; the
                    # callee acts on its own copy or a boundary-managed borrow.
                    params[binding_id].add_read(route)
                    for expr in inner:
                        self._visit(expr, params)
                else:
                    self._visit(argument, params)

    def _visit_place_argument(
        self,
        place: hir.Place,
        call: hir.FunctionCall,
        targets: list[hir.FunctionLiteral] | None,
        pairings: list[list[tuple[hir.AST, hir.Param | None]]] | None,
        params: dict[int, ParameterEffects],
    ) -> None:
        resolved = self._resolve_route(place.target, params)
        if resolved is None:
            # The place roots at a non-parameter binding; nothing to record
            # for this function's parameters beyond embedded index uses.
            for child in _iter_children(place.target):
                self._visit(child, params)
            return
        binding_id, route, inner = resolved
        for expr in inner:
            self._visit(expr, params)
        effects = params[binding_id]
        if targets is None or pairings is None:
            effects.add_opaque(route)
            return
        for target, pairs in zip(targets, pairings):
            parameter = next(
                (param for argument, param in pairs if argument is place),
                None,
            )
            if parameter is None or parameter.binding_id is None:
                effects.add_opaque(route)
                continue
            callee_effects = self.effects[id(target)].params.get(
                parameter.binding_id
            )
            if callee_effects is None:
                effects.add_opaque(route)
                continue
            effects.merge_translated(callee_effects, route)


def analyze_effects(root: hir.AST) -> ProgramEffects:
    """Compute parameter effect summaries for a checked program.

    ``root`` is the merged, typechecked HIR block. The analysis is a may
    analysis: absence of an effect is a guarantee, presence is not.
    """
    return _EffectAnalyzer(root).solve()
