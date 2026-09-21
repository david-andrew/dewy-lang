"""Finite inference of omitted public effect rows.

Inference variables are compiler identities, distinct from user row parameters.
Their least solution grows from function bodies and selected value-boundary
constraints. Unknown behavior stays unknown; negative contracts are checked
against the solution, never used to remove inconvenient possible effects.
"""
from collections import deque
from dataclasses import dataclass

from . import effect_rows as rows

PREFIX = 'inferred-effect:'
BINDING_PREFIX = PREFIX + 'binding:'


def pending(contract: rows.Contract | None) -> bool:
    return (contract is not None and contract.allowed is not None
            and any(name.startswith(PREFIX) for name in contract.allowed.variables))


def resolve(contract: rows.Contract | None, solutions: dict[str, rows.Row]) -> rows.Contract | None:
    if contract is None or contract.allowed is None:
        return contract
    return rows.Contract(rows.substitute(contract.allowed, solutions), contract.excluded)


@dataclass(frozen=True)
class Constraint:
    actual: rows.Contract | None
    required: rows.Contract | None


@dataclass(frozen=True)
class _Rule:
    targets: tuple[str, ...]
    source: rows.Row
    covered: rows.Row = rows.Row()


def _admitted(contract: rows.Contract | None) -> rows.Row:
    return contract.allowed if contract is not None and contract.allowed is not None else rows.Row(unknown=True)


def solve(definitions: dict[str, rows.Contract], constraints: tuple[Constraint, ...] = ()) -> dict[str, rows.Row]:
    """Solve body equations and lower bounds on inferred destination rows.

    A destination with several unknown rows conservatively gives each one the
    residual behavior. This is an upper bound, not a claim to infer a unique
    minimal partition. Explicit permissions need not also enter the variable.
    """
    rules = [_Rule((name,), _admitted(body)) for name, body in definitions.items()]
    for constraint in constraints:
        permitted = _admitted(constraint.required)
        targets = tuple(name for name in permitted.variables if name in definitions)
        if not targets or permitted.unknown:
            continue
        covered = rows.Row(permitted.atoms, tuple(name for name in permitted.variables if name not in targets))
        rules.append(_Rule(targets, _admitted(constraint.actual), covered))
    solutions = {name: rows.Row() for name in definitions}
    users: dict[str, set[int]] = {}
    for index, rule in enumerate(rules):
        for name in rule.source.variables:
            if name in definitions:
                users.setdefault(name, set()).add(index)
    pending_rules = deque(range(len(rules)))
    queued = set(pending_rules)
    while pending_rules:
        index = pending_rules.popleft()
        queued.remove(index)
        rule = rules[index]
        source = rows.substitute(rule.source, solutions)
        residual = rows.Row(
            tuple(atom for atom in source.atoms if not any(rows.covers(bound, atom) for bound in rule.covered.atoms)),
            tuple(name for name in source.variables if name not in rule.covered.variables),
            source.unknown,
        )
        for name in rule.targets:
            updated = rows.union(solutions[name], residual)
            if updated == solutions[name]:
                continue
            solutions[name] = updated
            for user in users.get(name, ()):
                if user not in queued:
                    pending_rules.append(user)
                    queued.add(user)
    return solutions


def satisfied(constraint: Constraint, solutions: dict[str, rows.Row]) -> bool:
    return rows.implies(resolve(constraint.actual, solutions), resolve(constraint.required, solutions))


def compatible(actual: rows.Contract | None, required: rows.Contract | None) -> bool:
    """Possibility check only; selected boundaries owe the solved implication.

    Overload probes must not record constraints. Known atoms/exclusions still
    participate; only the compiler's unresolved variables have bounds here.
    """
    if not pending(actual) and not pending(required):
        return rows.implies(actual, required)
    lower = {name: rows.Row() for name in actual.allowed.variables if name.startswith(PREFIX)} if pending(actual) else {}
    upper = {name: rows.Row(unknown=True) for name in required.allowed.variables if name.startswith(PREFIX)} if pending(required) else {}
    return rows.implies(resolve(actual, lower), resolve(required, upper))


def type_constraints(actual, required, seen=None):
    """Rows at an already selected structural boundary, with call variance."""
    from . import ty
    actual, required = (ty.unfold(ty.strip_refinement(t)) for t in (actual, required))
    if actual is required:
        return []
    seen = set() if seen is None else seen
    key = id(actual), id(required)
    if key in seen:
        return []
    seen.add(key)
    result = []
    if isinstance(actual, ty.FunctionType) and isinstance(required, ty.FunctionType):
        result.append(Constraint(actual.effects, required.effects))
        for a, b in zip(actual.pos_or_kw, required.pos_or_kw):
            result.extend(type_constraints(b.type, a.type, seen))
        actual_kw = {p.name: p for p in [*actual.pos_or_kw, *actual.kw_only]}
        for b in required.kw_only:
            a = actual_kw.get(b.name)
            if a is not None:
                result.extend(type_constraints(b.type, a.type, seen))
        result.extend(type_constraints(actual.ret, required.ret, seen))
    elif isinstance(actual, ty.ArrayType) and isinstance(required, ty.ArrayType):
        result.extend(type_constraints(actual.element, required.element, seen))
        result.extend(type_constraints(required.element, actual.element, seen))
    elif isinstance(actual, ty.ObjectType) and isinstance(required, ty.ObjectType):
        for field in required.fields:
            supplied = actual.field(field.name)
            if supplied is not None:
                result.extend(type_constraints(supplied.type, field.type, seen))
                if not required.immutable:
                    result.extend(type_constraints(field.type, supplied.type, seen))
    elif isinstance(actual, (ty.TypeOr, ty.TypeAnd)):
        for member in actual.items:
            result.extend(type_constraints(member, required, seen))
    elif isinstance(required, (ty.TypeOr, ty.TypeAnd)):
        for member in required.items:
            result.extend(type_constraints(actual, member, seen))
    elif isinstance(actual, ty.OverloadType):
        for member in actual.methods:
            result.extend(type_constraints(member, required, seen))
    elif isinstance(required, ty.OverloadType):
        for member in required.methods:
            result.extend(type_constraints(actual, member, seen))
    elif isinstance(actual, ty.SequenceType) and isinstance(required, ty.SequenceType) and len(actual.items) == len(required.items):
        for a, b in zip(actual.items, required.items):
            result.extend(type_constraints(a, b, seen))
    return result
