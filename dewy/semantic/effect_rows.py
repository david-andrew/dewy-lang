"""Public effect rows, separate from internal aggregate-access summaries.

An identity's key is supplied by name resolution: a nominal brand, a
parameter slot, or a generic binder identity. It is never a source spelling.
Rows describe possible behavior; an empty row is a guarantee. Unknown rows
and unresolved row parameters therefore cannot discharge negative promises.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Subject:
    kind: Literal['resource', 'parameter']
    key: str
    route: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Atom:
    family: str
    subject: Subject | None = None


@dataclass(frozen=True, slots=True)
class Row:
    atoms: tuple[Atom, ...] = ()
    variables: tuple[str, ...] = ()
    unknown: bool = False


@dataclass(frozen=True, slots=True)
class Contract:
    # None means infer an open row, not the empty row.
    allowed: Row | None = None
    excluded: tuple[Atom, ...] = ()


def subject_covers(wide: Subject, narrow: Subject) -> bool:
    if wide.kind != narrow.kind or wide.key != narrow.key:
        return False
    if wide.kind == 'resource':
        return wide == narrow  # nominal inheritance grants no effect authority
    return narrow.route[:len(wide.route)] == wide.route


def covers(wide: Atom, narrow: Atom) -> bool:
    """Positive permissions: a subjectless atom is not a family wildcard."""
    if wide.family != narrow.family:
        return False
    if wide.subject is None or narrow.subject is None:
        return wide.subject == narrow.subject
    return subject_covers(wide.subject, narrow.subject)


def overlaps(exclusion: Atom, possible: Atom) -> bool:
    """A bare negative family excludes every subject, unlike a positive atom."""
    if exclusion.family != possible.family:
        return False
    if exclusion.subject is None:
        return True
    if possible.subject is None:
        return False
    return subject_covers(exclusion.subject, possible.subject) or subject_covers(possible.subject, exclusion.subject)


def union(*rows: Row) -> Row:
    atoms: list[Atom] = []
    variables: list[str] = []
    unknown = False
    for row in rows:
        unknown |= row.unknown
        for atom in row.atoms:
            if any(covers(old, atom) for old in atoms):
                continue
            atoms = [old for old in atoms if not covers(atom, old)]
            atoms.append(atom)
        for variable in row.variables:
            if variable not in variables:
                variables.append(variable)
    # Stable identity independent of encounter/call-graph traversal order.
    atoms.sort(key=lambda atom: (atom.family, '' if atom.subject is None else atom.subject.kind,
                                '' if atom.subject is None else atom.subject.key,
                                () if atom.subject is None else atom.subject.route))
    return Row(tuple(atoms), tuple(sorted(variables)), unknown)


def subset(actual: Row, permitted: Row) -> bool:
    if permitted.unknown:
        return True
    if actual.unknown or not set(actual.variables) <= set(permitted.variables):
        return False
    return all(any(covers(bound, atom) for bound in permitted.atoms) for atom in actual.atoms)


def satisfies(actual: Row, contract: Contract) -> bool:
    if contract.allowed is not None and not subset(actual, contract.allowed):
        return False
    if contract.excluded and (actual.unknown or actual.variables):
        return False
    return not any(overlaps(excluded, atom) for excluded in contract.excluded for atom in actual.atoms)


def substitute(row: Row, rows: dict[str, Row], subjects: dict[str, Subject | None] | None = None) -> Row:
    """Instantiate row binders and parameter routes at a call boundary.

    A resolved by-value argument maps to None: its local storage is not an
    external resource. Missing mappings stay symbolic, never silently pure.
    Substitution is simultaneous, so a caller's E is not recursively captured
    by the callee's mapping for E.
    """
    atoms = []
    for atom in row.atoms:
        subject = atom.subject
        if subject is not None and subject.kind == 'parameter' and subjects is not None and subject.key in subjects:
            supplied = subjects[subject.key]
            if supplied is None:
                continue
            subject = Subject(supplied.kind, supplied.key, supplied.route + subject.route)
        atoms.append(Atom(atom.family, subject))
    output = Row(tuple(atoms), unknown=row.unknown)
    return union(output, *(rows.get(variable, Row(variables=(variable,))) for variable in row.variables))


def implies(actual: Contract | None, required: Contract | None) -> bool:
    """Whether every behavior admitted by actual satisfies required."""
    if required is None:
        return True
    actual = actual or Contract()
    admitted = actual.allowed or Row(unknown=True)
    if required.allowed is not None and not subset(admitted, required.allowed):
        return False
    for exclusion in required.excluded:
        # A closed row can establish absence directly. An open row must
        # explicitly exclude at least the same family/route.
        if not admitted.unknown and not admitted.variables and not any(overlaps(exclusion, atom) for atom in admitted.atoms):
            continue
        if not any(old.family == exclusion.family and (old.subject is None or
                   exclusion.subject is not None and subject_covers(old.subject, exclusion.subject))
                   for old in actual.excluded):
            return False
    return True


def identity(contract: Contract | None) -> str:
    """Canonical key for signature interning and cache identity."""
    if contract is None:
        return ''
    import json

    def atom_key(atom: Atom):
        return (atom.family, None if atom.subject is None else (atom.subject.kind, atom.subject.key, atom.subject.route))

    allowed = None if contract.allowed is None else union(contract.allowed)
    return json.dumps((None if allowed is None else (
        [atom_key(atom) for atom in allowed.atoms], allowed.variables, allowed.unknown),
        sorted({json.dumps(atom_key(atom)) for atom in contract.excluded})), separators=(',', ':'))


def display(contract: Contract | None, parameter_names: dict[str, str]) -> str:
    """Diagnostic spelling; nominal keys use the same display as minted types."""
    if contract is None:
        return ''

    def atom_text(atom):
        if atom.subject is None:
            return atom.family
        subject = atom.subject
        name = parameter_names.get(subject.key, f'parameter#{subject.key}') if subject.kind == 'parameter' else subject.key
        return f'{atom.family}<{".".join((name, *subject.route))}>'

    terms = []
    if contract.allowed is not None:
        row = union(contract.allowed)
        terms.extend(atom_text(atom) for atom in row.atoms)
        terms.extend(row.variables)
        if row.unknown:
            terms.append('<unknown effects>')
        if not terms:
            terms.append('no_effects')
    terms.extend(f'no {atom_text(atom)}' for atom in contract.excluded)
    return ''.join(f' & {term}' for term in terms)


def join(*contracts: Contract) -> Contract:
    """Effects of a sequence or alternatives, retaining shared exclusions.

    An open negative callback must not become an unqualified unknown row.
    A guarantee survives only when every participating operation implies it.
    """
    allowed = union(*(item.allowed for item in contracts)) if all(item.allowed is not None for item in contracts) else None
    candidates = dict.fromkeys(atom for item in contracts for atom in item.excluded)
    excluded = tuple(atom for atom in candidates if all(implies(item, Contract(excluded=(atom,))) for item in contracts))
    return Contract(allowed, excluded)


def instantiate(contract: Contract, subjects: dict[str, Subject | None], *, max_depth: int = 8) -> Contract:
    """Translate a call boundary, widening deep positive routes only.

    Truncating an exclusion would strengthen it, so deep exclusions drop.
    Likewise an exclusion of private storage disappears, not its subject:
    losing just the subject would accidentally forbid an entire family.
    """
    def bounded(atom):
        subject = atom.subject
        if subject is not None and len(subject.route) > max_depth:
            return Atom(atom.family, Subject(subject.kind, subject.key, subject.route[:max_depth]))
        return atom

    allowed = substitute(contract.allowed, {}, subjects) if contract.allowed is not None else None
    if allowed is not None:
        allowed = union(Row(tuple(bounded(atom) for atom in allowed.atoms), allowed.variables, allowed.unknown))
    excluded = substitute(Row(contract.excluded), {}, subjects).atoms
    return Contract(allowed, tuple(atom for atom in excluded if atom.subject is None or len(atom.subject.route) <= max_depth))


def bind_receiver(contract: Contract | None, parameter_count: int) -> Contract | None:
    """Expose a method without its hidden receiver slot.

    Receiver effects become unknown until bound-receiver subjects are modeled;
    removing the slot must never turn those effects into an empty guarantee.
    """
    if contract is None:
        return None
    subjects = {str(i): Subject('parameter', str(i - 1)) for i in range(1, parameter_count)}
    subjects['0'] = None
    bound = instantiate(contract, subjects)
    if contract.allowed is not None and any(atom.subject is not None and atom.subject.kind == 'parameter' and atom.subject.key == '0' for atom in contract.allowed.atoms):
        bound = Contract(union(bound.allowed, Row(unknown=True)), bound.excluded)
    return bound
