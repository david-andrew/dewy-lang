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
mutated, rebound, and escaped. Raw memory intrinsics and system calls have
no boundary of their own, so an aggregate parameter route handed to one (or
reinterpreted by a non-scalar transmute) escapes; every other callee is a
value boundary that decides for itself.

The first consumer is the udewy lowering pass, which uses these summaries to
decide when a value-semantic call boundary may borrow the caller's storage
instead of copying, replacing the array-specific boundary checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque

from .. import bindings as sb
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
    if not routes:
        return False
    # Route depth is bounded, whereas a parameter may have many sibling
    # fields. Probe its prefixes instead of scanning every stored sibling.
    for length in range(len(route) + 1):
        if route[:length] in routes:
            return True
    return False


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

    def read_only_at(self, route: Route) -> bool:
        """No write or exposure overlaps this projection's storage.

        Ancestor replacement and descendant mutation both conflict. Sibling
        record fields do not; array indices deliberately share one wildcard
        step, so this does not assume that two selections are disjoint.
        """
        return all(not (route[:len(other)] == other or other[:len(route)] == route)
                   for routes in (self.mutates, self.rebinds, self.escapes)
                   for other in routes)

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
        if other is self:
            # Recursive field forwarding may add/remove routes in this very
            # summary. Propagate a snapshot, then let the worklist revisit it.
            other = other.copy()
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


def _literal_params(literal: hir.FunctionLiteral) -> list[hir.Param]:
    params = [*literal.pos_or_kw_args, *literal.kw_only_args]
    if literal.rest_args is not None:
        params.append(literal.rest_args)
    return params


class _EffectAnalyzer:
    def __init__(self, root: hir.AST):
        self.root = root
        self.literals: list[hir.FunctionLiteral] = []
        self.calls: list[hir.FunctionCall] = []
        self.declares: dict[int, hir.Declare] = {}
        self.reassigned: set[int] = set()
        self.param_binding_ids: set[int] = set()
        self.collected: set[int] = set()
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
        # callee -> (caller, caller parameter, callee parameter, route prefix)
        # All these routes come from checked syntax, independent of summaries.
        self.transfers: dict[int, set[tuple[int, int, int, Route]]] = {}

    # ------------------------------------------------------------------
    # program structure collection

    def _collect(self, node: object) -> None:
        if isinstance(node, hir.AST):
            if id(node) in self.collected:
                return
            self.collected.add(id(node))
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
        elif isinstance(node, hir.FunctionCall):
            self.calls.append(node)
        if isinstance(node, hir.AST):
            for child in hir.children(node):
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

    def _value_targets(self, node: hir.AST, selected: int | None = None) -> list[hir.FunctionLiteral] | None:
        """Resolve runtime choices separately from overload dispatch order.

        Apply a selection inside each possible value. Visit a shared choice
        once, so chains of conditional aliases do not enumerate every path.
        Unknown arms and cycles retain the ordinary conservative boundary.
        """
        def select(targets):
            if selected is not None:
                return [targets[selected]] if selected < len(targets) else None
            return targets or None

        targets = self._flatten_callable(node, frozenset())
        if targets is not None:
            return select(targets)  # ordinary direct calls keep their fast path
        node = _unwrap(node)
        if isinstance(node, hir.ExpressedIdentifier):
            if (node.binding_id is None or node.binding_id in self.param_binding_ids
                    or node.binding_id in self.reassigned or node.binding_id not in self.declares):
                return None
        elif not isinstance(node, (hir.ValueCast, hir.Flow)):
            return None
        pending = [(node, False)]
        active, done, result = set(), set(), {}
        while pending:
            node, leaving = pending.pop()
            node = _unwrap(node)
            key = id(node)
            if leaving:
                active.remove(key)
                done.add(key)
                continue
            if key in active:
                return None
            if key in done:
                continue
            active.add(key)
            pending.append((node, True))
            if isinstance(node, (hir.FunctionLiteral, hir.OverloadedFunction)):
                targets = self._flatten_callable(node, frozenset())
                if targets is None or (targets := select(targets)) is None:
                    return None
                result.update((id(target), target) for target in targets)
            elif isinstance(node, hir.ValueCast):
                pending.append((node.expr, False))
            elif isinstance(node, hir.ExpressedIdentifier):
                binding = node.binding_id
                if (binding is None or binding in self.param_binding_ids
                        or binding in self.reassigned or binding not in self.declares):
                    return None
                pending.append((self.declares[binding].expr, False))
            elif isinstance(node, hir.Flow) and node.default is not None and all(isinstance(arm, hir.IfArm) for arm in node.arms):
                pending.append((node.default, False))
                pending.extend((arm.body, False) for arm in reversed(node.arms))
            else:
                return None
        return list(result.values()) or None

    def _direct_targets(self, call: hir.FunctionCall) -> list[hir.FunctionLiteral] | None:
        return self._value_targets(call.func, call.selected_method_index)

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
        # Scan each body/default once for local effects and place-call edges.
        # Then solve those additive equations without traversing HIR again.
        # Prefix normalization and MAX_ROUTE_DEPTH bound recursive forwarding;
        # ordinary value arguments never introduce a transfer edge.
        for literal in self.literals:
            self.current_literal = id(literal)
            self.effects[id(literal)] = self._summarize(literal)
        pending = deque(self.effects)
        queued = set(pending)
        while pending:
            key = pending.popleft()
            queued.remove(key)
            source = self.effects[key].params
            for caller, caller_param, callee_param, prefix in self.transfers.get(key, ()):
                target = self.effects[caller].params[caller_param]
                if target.merge_translated(source[callee_param], prefix) and caller not in queued:
                    queued.add(caller)
                    pending.append(caller)
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
        for parameter in _literal_params(literal):
            if isinstance(parameter, hir.BoundParam):
                self._visit(parameter.value, params)
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
        path = sb.access_path(node, unwrap=_unwrap)
        binding_id = path.binding_id
        if binding_id is None or binding_id not in params:
            return None
        route = tuple(INDEX_STEP if isinstance(step, hir.Index) else step.name for step in path.steps)
        inner = [step.index for step in reversed(path.steps) if isinstance(step, hir.Index)]
        return binding_id, route, inner

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
            for child in hir.children(node):
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
        if isinstance(node, hir.DictStore):
            for array in (node.keys, *([node.values] if node.values is not None else [])):
                resolved = self._resolve_route(array, params)
                if resolved is not None:
                    binding_id, route, inner = resolved
                    params[binding_id].add_mutate(route)
                    for expr in inner:
                        self._visit(expr, params)
                else:
                    self._visit(array, params)
            self._visit(node.key, params)
            if node.value is not None:
                self._visit(node.value, params)
            return
        if isinstance(node, hir.DictEntries):
            self._visit(node.dictionary, params)
            return
        if isinstance(node, hir.SetAlgebra):
            self._visit(node.left, params)
            self._visit(node.right, params)
            return
        if isinstance(node, hir.DictView):
            self._visit(node.dictionary, params)
            return
        if isinstance(node, hir.DictRemove):
            for array in (node.keys, *([node.values] if node.values is not None else [])):
                resolved = self._resolve_route(array, params)
                if resolved is not None:
                    binding_id, route, inner = resolved
                    params[binding_id].add_mutate(route)
                    for expr in inner:
                        self._visit(expr, params)
                else:
                    self._visit(array, params)
            if node.key is not None:
                self._visit(node.key, params)
            if node.default is not None:
                self._visit(node.default, params)
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
        if isinstance(node, hir.Transmute):
            # Reinterpreting scalar bits exposes nothing. A pointer or
            # aggregate transmute hands the storage itself to whatever
            # consumes the result.
            if _word_type(node.type) and _word_type(node.expr.type):
                self._visit(node.expr, params)
                return
            resolved = self._resolve_route(node.expr, params)
            if resolved is None:
                self._visit(node.expr, params)
                return
            binding_id, route, inner = resolved
            params[binding_id].add_read(route)
            params[binding_id].add_escape(route)
            for expr in inner:
                self._visit(expr, params)
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
        for child in hir.children(node):
            self._visit(child, params)

    def _visit_call(
        self,
        call: hir.FunctionCall,
        params: dict[int, ParameterEffects],
    ) -> None:
        if isinstance(call.func, hir.ArrayMethod):
            # Joining reads the receiver; growth/reordering methods mutate it.
            # Argument expressions still contribute their own effects below.
            resolved = self._resolve_route(call.func.array, params)
            if resolved is not None:
                binding_id, route, inner = resolved
                if call.func.name == 'join':
                    params[binding_id].add_read(route)
                else:
                    params[binding_id].add_mutate(route)
                for expr in inner:
                    self._visit(expr, params)
            else:
                self._visit(call.func.array, params)
            for argument in [*call.pos_args, *call.kw_args.values()]:
                self._visit(argument, params)
            return
        self._visit(call.func, params)
        raw = self._raw_callee(call)
        arguments = [*call.pos_args, *call.kw_args.values()]
        # Only a place can carry the callee's effects back to this function's
        # parameters. Ordinary arguments still evaluate, but target resolution
        # and parameter pairing cannot contribute to their read-only boundary.
        targets = self._direct_targets(call) if any(isinstance(arg, hir.Place) for arg in arguments) else None
        pairings: list[list[tuple[hir.AST, hir.Param | None]]] | None = None
        if targets is not None:
            resolved_pairs = [
                self._pair_arguments(call, target) for target in targets
            ]
            if all(pairs is not None for pairs in resolved_pairs):
                pairings = [pairs for pairs in resolved_pairs if pairs is not None]
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
                    if raw and not _word_type(argument.type):
                        params[binding_id].add_escape(route)
                    for expr in inner:
                        self._visit(expr, params)
                else:
                    self._visit(argument, params)

    @staticmethod
    def _raw_callee(call: hir.FunctionCall) -> bool:
        """Raw memory operations and system calls may read or write through
        any storage they receive, and have no prologue of their own to copy
        it. An aggregate handed to one escapes: its summary then says so, and
        a caller borrowing against that summary sees the exposure at this
        boundary rather than through a whole-call-graph bit. Every other
        callee, resolved or not, is a value boundary that decides for itself."""
        function = _unwrap(call.func)
        if not isinstance(function, hir.ExpressedIdentifier) or function.binding_id is not None:
            return False
        name = function.name
        return name.startswith(('__load_', '__store_', '__syscall')) or name in ('__load__', '__store__')

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
            for child in hir.children(place.target):
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
            self.transfers.setdefault(id(target), set()).add(
                (self.current_literal, binding_id, parameter.binding_id, route)
            )


_WORD_NAMES = frozenset(['int', 'uint', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64', 'float32', 'float64', 'bool', 'true', 'false', 'none'])


def _word_type(type_: ty.Type) -> bool:
    """A word carries no storage: passing it to a raw operation exposes nothing."""
    plain = ty.unfold(ty.strip_refinement(type_))
    if isinstance(plain, ty.IntegerLiteralType):
        return -9223372036854775808 <= plain.value <= 18446744073709551615
    return isinstance(plain, str) and plain in _WORD_NAMES


def analyze_effects(root: hir.AST) -> ProgramEffects:
    """Compute parameter effect summaries for a checked program.

    ``root`` is the merged, typechecked HIR block. The analysis is a may
    analysis: absence of an effect is a guarantee, presence is not.
    """
    return _EffectAnalyzer(root).solve()


@dataclass(frozen=True)
class PlaceLoans:
    nonescaping: frozenset[int]
    fixed_storage: frozenset[int]


def preserves_storage(summary: ParameterEffects, type_) -> bool:
    """A whole frame owner must keep its layout and backing storage.

    Read-only arrays keep their descriptor. Scalar records may change fields,
    but an opaque root mutation or replacement still excludes placement.
    Candidate selection separately rules out resource and aggregate fields.
    """
    return not summary.escapes and (summary.read_only or (
        isinstance(ty.structural_base(type_), ty.ObjectType)
        and ROOT not in summary.mutates and ROOT not in summary.rebinds))


def place_loans(analysis: _EffectAnalyzer, summaries: ProgramEffects) -> PlaceLoans:
    """Call-only addresses and whole owners whose storage stays fixed.

    Every target and repeated argument position must establish each guarantee.
    Reuse collected call sites and solved summaries, without another HIR walk.
    """
    safe, unsafe, fixed, changed = set(), set(), set(), set()
    for call in analysis.calls:
        places = {id(arg) for arg in [*call.pos_args, *call.kw_args.values()] if isinstance(arg, hir.Place)}
        if not places:
            continue
        targets = analysis._direct_targets(call)
        if not targets:
            unsafe.update(places)
            continue
        for target in targets:
            paired = set()
            for argument, parameter in analysis._pair_arguments(call, target) or ():
                key = id(argument)
                if key not in places:
                    continue
                paired.add(key)
                summary = summaries.for_param_binding(parameter.binding_id) if parameter is not None else None
                if summary is None or summary.escapes:
                    unsafe.add(key)
                else:
                    safe.add(key)
                    (fixed if preserves_storage(summary, argument.type) else changed).add(key)
            unsafe.update(places - paired)
    return PlaceLoans(frozenset(safe - unsafe), frozenset(fixed - unsafe - changed))


def read_only_places(root: hir.AST, context: hir.AST | None = None) -> set[int]:
    """Places whose callees neither write nor retain their borrowed storage.

    This is the same transitive may-effect proof used for storage borrows.
    A missing body, unresolved callback, or ambiguous parameter pairing is
    not evidence of a read-only call. Argument evaluation is still separate.
    """
    calls = [(node, [arg for arg in [*node.pos_args, *node.kw_args.values()] if isinstance(arg, hir.Place)])
             for node in hir.walk(root) if isinstance(node, hir.FunctionCall)]
    calls = [(call, places) for call, places in calls if places]
    if not calls:
        return set()
    analysis = _EffectAnalyzer(root if context is None else context)
    summaries = analysis.solve()
    safe, unsafe = set(), set()
    for call, places in calls:
        targets = analysis._direct_targets(call)
        for place in places:
            readonly = targets is not None
            for target in targets or ():
                pairs = analysis._pair_arguments(call, target)
                parameter = next((p for arg, p in pairs or () if arg is place), None)
                summary = summaries.for_param_binding(parameter.binding_id) if parameter is not None else None
                if summary is None or not summary.read_only:
                    readonly = False
                    break
            (safe if readonly else unsafe).add(id(place))
    return safe - unsafe


def analyze_global_writes(root: hir.AST, globals: set[int]) -> dict[int, set[int]]:
    """May-write roots for each call, including transitive/default effects.

    Reuse direct-call resolution from parameter effects. Scan each body once,
    then propagate finite sets through the call graph. Unknown calls may write
    every tracked global; creating a nested function does not execute its body.
    Borrowed endpoints are tracked separately by read_only_places.
    """
    if not globals:
        return {}
    from .predicate_effects import mutated_bindings

    analysis = _EffectAnalyzer(root)
    calls = {id(node): node for node in hir.walk(root) if isinstance(node, hir.FunctionCall)}
    targets = {
        # A checked intrinsic has no lexical binding. integer_operation is
        # numeric meaning, not a purity promise for a library implementation.
        key: [] if isinstance(call.func, hir.ArrayMethod) or (
            isinstance(call.func, hir.ExpressedIdentifier) and call.func.binding_id is None
        ) else analysis._direct_targets(call)
        for key, call in calls.items()
    }
    summaries: dict[int, set[int]] = {}
    callers: dict[int, set[int]] = {}
    for literal in analysis.literals:
        key = id(literal)
        expressions = [literal.body, *(p.value for p in _literal_params(literal) if isinstance(p, hir.BoundParam))]
        writes: set[int] = set()
        for expression in expressions:
            writes.update(mutated_bindings(expression) & globals)
            pending = [expression]
            while pending:
                node = pending.pop()
                if isinstance(node, hir.FunctionLiteral):
                    continue
                if isinstance(node, hir.FunctionCall):
                    resolved = targets[id(node)]
                    if resolved is None:
                        writes.update(globals)
                    else:
                        for callee in resolved:
                            callers.setdefault(id(callee), set()).add(key)
                pending.extend(hir.children(node))
        summaries[key] = writes
    pending = deque(summaries)
    queued = set(pending)
    while pending:
        callee = pending.popleft()
        queued.remove(callee)
        for caller in callers.get(callee, ()):
            incoming = summaries[callee] - summaries[caller]
            if incoming:
                summaries[caller].update(incoming)
                if caller not in queued:
                    queued.add(caller)
                    pending.append(caller)
    return {
        key: set(globals) if resolved is None else set().union(*(summaries[id(callee)] for callee in resolved))
        for key, resolved in targets.items()
    }


def nonlocal_bindings(root: hir.AST) -> set[int]:
    """Lexical captures and globals, excluding each function's own storage.

    This lets mutation queries track captured receivers without treating a
    recursive callee's local binding ids as the caller's current activation.
    """
    result = set()
    for literal in hir.walk(root):
        if not isinstance(literal, hir.FunctionLiteral):
            continue
        params = _literal_params(literal)
        local = {param.binding_id for param in params}
        reads = set()
        pending = [literal.body, *(p.value for p in params if isinstance(p, hir.BoundParam))]
        seen = set()
        while pending:
            node = pending.pop()
            if id(node) in seen or isinstance(node, hir.FunctionLiteral):
                continue
            seen.add(id(node))
            if isinstance(node, hir.Declare):
                local.add(node.binding_id)
            elif isinstance(node, hir.IteratorExpression):
                local.add(node.target.binding_id)
            elif isinstance(node, hir.ExpressedIdentifier) and node.binding_id is not None:
                reads.add(node.binding_id)
            pending.extend(hir.children(node))
        result.update(reads - local)
    return result
