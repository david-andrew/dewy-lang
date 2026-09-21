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
