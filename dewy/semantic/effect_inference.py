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
class Projection:
    """One call equation, with subjects still in the callee's parameter scope.

    This transient solver input is not a source type or a serialized binder.
    Apply its environment after resolving the source row, never before.
    """
    source: rows.Contract
    subjects: dict[str, rows.Subject | None]


@dataclass(frozen=True)
class _Rule:
    targets: tuple[str, ...]
    source: rows.Row
    covered: rows.Row = rows.Row()
    subjects: dict[str, rows.Subject | None] | None = None


def _admitted(contract: rows.Contract | None) -> rows.Row:
    return contract.allowed if contract is not None and contract.allowed is not None else rows.Row(unknown=True)


def solve(definitions: dict[str, rows.Contract], constraints: tuple[Constraint, ...] = (),
          projections: dict[str, Projection] | None = None) -> dict[str, rows.Row]:
    """Solve body equations and lower bounds on inferred destination rows.

    A destination with several unknown rows conservatively gives each one the
    residual behavior. This is an upper bound, not a claim to infer a unique
    minimal partition. Explicit permissions need not also enter the variable.
    """
    projections = projections or {}
    names = definitions.keys() | projections.keys()
    rules = [_Rule((name,), _admitted(body)) for name, body in definitions.items()]
    rules.extend(_Rule((name,), _admitted(edge.source), subjects=edge.subjects)
                 for name, edge in projections.items())
    for constraint in constraints:
        permitted = _admitted(constraint.required)
        targets = tuple(name for name in permitted.variables if name in definitions)
        if not targets or permitted.unknown:
            continue
        covered = rows.Row(permitted.atoms, tuple(name for name in permitted.variables if name not in targets))
        rules.append(_Rule(targets, _admitted(constraint.actual), covered))
    solutions = {name: rows.Row() for name in names}
    users: dict[str, set[int]] = {}
    for index, rule in enumerate(rules):
        for name in rule.source.variables:
            if name in names:
                users.setdefault(name, set()).add(index)
    pending_rules = deque(range(len(rules)))
    queued = set(pending_rules)
    while pending_rules:
        index = pending_rules.popleft()
        queued.remove(index)
        rule = rules[index]
        source = rows.substitute(rule.source, solutions)
        if rule.subjects is not None:
            source = _admitted(rows.instantiate(rows.Contract(source), rule.subjects))
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



def resolve_contracts(contract: rows.Contract | None, solutions: dict[str, rows.Contract]) -> rows.Contract | None:
    """Substitute inferred rows without throwing away negative guarantees.

    A sequence retains only exclusions shared by its pieces. Written outer
    exclusions remain part of the original contract, independently of which
    variable carried a guarantee during inference.
    """
    return rows.replace_contracts(contract, solutions)


def _projection_candidates(vocabulary, projections):
    """Carry demanded exclusions backwards through call environments.

    An inverse translation only renames a slot or removes a route prefix.
    Candidate routes are therefore suffixes of the finite initial vocabulary,
    even for recursive calls. Candidates still need proof by every rule.
    """
    inverse = {}
    for edge in projections.values():
        for slot, subject in edge.subjects.items():
            if subject is not None and subject.kind == 'parameter':
                inverse.setdefault(subject.key, set()).add((slot, subject.route))
    pending = deque(vocabulary)
    while pending:
        atom = pending.popleft()
        subject = atom.subject
        if subject is None or subject.kind != 'parameter':
            continue
        for slot, prefix in inverse.get(subject.key, ()):
            if subject.route[:len(prefix)] != prefix:
                continue
            candidate = rows.Atom(atom.family, rows.Subject('parameter', slot, subject.route[len(prefix):]))
            if candidate not in vocabulary:
                vocabulary[candidate] = None
                pending.append(candidate)


def solve_contracts(definitions: dict[str, rows.Contract], constraints: tuple[Constraint, ...] = (),
                    projections: dict[str, Projection] | None = None) -> dict[str, rows.Contract]:
    """Possible effects grow; proven absences shrink over a finite vocabulary.

    Exclusions mentioned by bodies or obligations select candidates only.
    Every body and incoming assignment must establish each surviving candidate.
    An unknown operation therefore removes an unsupported candidate even in a
    recursive component. The positive fixed point remains authoritative.
    """
    projections = projections or {}
    positive = solve(definitions, constraints, projections)
    vocabulary = dict.fromkeys(atom for body in definitions.values() for atom in body.excluded)
    for projection in projections.values():
        vocabulary.update(dict.fromkeys(projection.source.excluded))
    for edge in constraints:
        for contract in (edge.actual, edge.required):
            if contract is not None:
                vocabulary.update(dict.fromkeys(contract.excluded))
    if not vocabulary:
        return {name: rows.Contract(row) for name, row in positive.items()}
    _projection_candidates(vocabulary, projections)
    rules = [(name, body, rows.Row(), None) for name, body in definitions.items()]
    rules.extend((name, edge.source, rows.Row(), edge.subjects) for name, edge in projections.items())
    for edge in constraints:
        admitted = _admitted(edge.required)
        targets = tuple(name for name in admitted.variables if name in definitions)
        if not targets or admitted.unknown:
            continue
        covered = rows.Row(admitted.atoms, tuple(name for name in admitted.variables if name not in targets))
        rules.extend((name, edge.actual or rows.Contract(), covered, None) for name in targets)
    solutions = {name: rows.Contract(row, tuple(vocabulary)) for name, row in positive.items()}
    users: dict[str, set[int]] = {}
    for index, (_, body, _, _) in enumerate(rules):
        for name in _admitted(body).variables:
            if name in solutions:
                users.setdefault(name, set()).add(index)
    work = deque(range(len(rules)))
    queued = set(work)
    while work:
        index = work.popleft()
        queued.remove(index)
        name, body, covered, subjects = rules[index]
        actual = resolve_contracts(body, solutions)
        if subjects is not None:
            actual = rows.instantiate(actual, subjects)
        admitted = _admitted(actual)
        residual = rows.Contract(rows.Row(
            tuple(atom for atom in admitted.atoms if not any(rows.covers(bound, atom) for bound in covered.atoms)),
            tuple(variable for variable in admitted.variables if variable not in covered.variables),
            admitted.unknown,
        ), actual.excluded)
        previous = solutions[name]
        kept = tuple(atom for atom in previous.excluded if rows.implies(residual, rows.Contract(excluded=(atom,))))
        if kept == previous.excluded:
            continue
        solutions[name] = rows.Contract(previous.allowed, kept)
        for user in users.get(name, ()):
            if user not in queued:
                work.append(user)
                queued.add(user)
    return solutions


def satisfied_contracts(constraint: Constraint, solutions: dict[str, rows.Contract]) -> bool:
    return rows.implies(resolve_contracts(constraint.actual, solutions), resolve_contracts(constraint.required, solutions))
