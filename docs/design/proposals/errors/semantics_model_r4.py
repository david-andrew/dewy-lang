"""R4 reference algebra and ordinary-library recovery prototype.
No Dewy parser, typechecker, ownership, ABI, allocator, or actual scheduler is modeled.
Gate events model a required ordering, not proof of atomic side-effect admission.
Context tuples are a correctness representation, not the proposed shared-path cost model.
"""
from dataclasses import dataclass, field, replace
from itertools import count, permutations, product

frame_ids = count()

@dataclass(frozen=True)
class Frame:
    identity: int
    text: str
    site: str

@dataclass(frozen=True)
class Failure:
    kind: str
    occurrence: int
    children: tuple = ()
    context: tuple = ()
    origin: object = "constructed"
    payload: tuple = ()
    canceled: bool = field(init=False)

    def __post_init__(self):
        if self.kind == "ErrorGroup":
            assert self.children, "empty groups are not failures"
        else:
            assert not self.children
        object.__setattr__(self, "canceled", self.kind == "Canceled" or any(c.canceled for c in self.children))
        if self.kind == "none":
            object.__setattr__(self, "origin", None)

    @property
    def group(self):
        return self.kind == "ErrorGroup"

    @property
    def ordinary(self):
        return self.kind not in {"ErrorGroup", "Canceled", "none", "Stop"}

    @property
    def message(self):
        return "multiple failures" if self.group else dict(self.payload).get("message")


def group(children, *, source=None, site="combine-site"):
    assert children
    if source is None:
        return Failure("ErrorGroup", -1, tuple(children), origin=site)
    return replace(source, children=tuple(children))


def combine(a, b, *, site="combine-site"):
    if not isinstance(a, Failure) or not isinstance(b, Failure):
        raise TypeError("& requires two failure operands")
    return group((a, b), site=site)


def join(*failures, site="combine-site"):
    if not all(isinstance(e, Failure) for e in failures):
        raise TypeError("join accepts failures only")
    if not failures:
        return None                      # model success-void, NOT Failure('none', ...)
    if len(failures) == 1:
        return failures[0]
    return group(failures, site=site)


def with_context(e, text, *, site="context-site"):
    frame = Frame(next(frame_ids), text, site)
    return replace(e, context=(frame,) + e.context)


def path_context(ancestors, local):
    # An inherited view must not repeat the exact ancestor frame if re-embedded.
    ancestor_ids = {f.identity for f in ancestors}
    return ancestors + tuple(f for f in local if f.identity not in ancestor_ids)


def leaves(e):
    pending = [(e, ())]
    while pending:
        node, ancestors = pending.pop()
        path = path_context(ancestors, node.context)
        if node.group:
            pending.extend((c, path) for c in reversed(node.children))
        else:
            yield replace(node, context=path)


def matches_root(e, selectors):
    return (e.kind in selectors or "exception" in selectors
            or (e.ordinary and "error" in selectors))


def propagate(e, selectors=None):
    if selectors is None or matches_root(e, selectors):
        return "forward"
    if "Canceled" in selectors and e.canceled:
        return "forward"
    return "retain"


def default(e, selectors=None):
    selected = selectors is None or matches_root(e, selectors)
    acknowledged = selectors is not None and "Canceled" in selectors
    if e.canceled and not (selected and acknowledged):
        return "forward"
    return "default" if selected else "retain"


def reconstruct(source, kids):
    kids = tuple(k for k in kids if k is not None)
    if not kids:
        return None
    if len(kids) == len(source.children) and all(a is b for a, b in zip(kids, source.children)):
        return source
    return group(kids, source=source)      # preserve unary context/origin boundary


def split(e, selectors):
    """Advanced deferred API; used here to check the underlying partition algebra."""
    if "ErrorGroup" in selectors:
        raise TypeError("split selects leaves")
    stack, results = [(e, False)], []
    while stack:
        item, visited = stack.pop()
        if not item.group:
            results.append((item, None) if matches_root(item, selectors) else (None, item))
        elif not visited:
            stack.append((item, True))
            stack.extend((c, False) for c in reversed(item.children))
        else:
            n = len(item.children)
            pairs = results[-n:]
            del results[-n:]
            results.append(tuple(reconstruct(item, [p[side] for p in pairs]) for side in (0, 1)))
    yes, no = results[0]
    return ([] if yes is None else [yes], [] if no is None else [no])


class Gate:
    """Synthetic task cancellation delivered at named admission/check boundaries."""
    def __init__(self, cancel_at=()):
        self.cancel_at = set(cancel_at)
        self.canceled = False
        self.calls = []

    def check(self, point):
        self.calls.append(point)
        if point in self.cancel_at:
            self.canceled = True
        if self.canceled:
            return Failure("Canceled", -2, origin=point)
        return None


def recover(failure, selectors, repair, gate):
    """Prototype keeps remainder internally. Selected payloads assumed copyable here."""
    if "ErrorGroup" in selectors or "Canceled" in selectors or "exception" in selectors:
        raise TypeError("v1 recovery selects ordinary error leaves")
    if failure.canceled:
        return failure, []                # M1: BEFORE gates, traversal or callback setup
    stopped = gate.check("entry")
    if stopped is not None:
        return combine(failure, stopped), []
    stack, results, attempted = [(failure, False, ())], [], []
    canceled_by_task = None
    while stack:
        node, visited, ancestors = stack.pop()
        path = path_context(ancestors, node.context)
        if node.group:
            if not visited:
                stack.append((node, True, ancestors))
                stack.extend((c, False, path) for c in reversed(node.children))
            else:
                n = len(node.children)
                kids = results[-n:]
                del results[-n:]
                results.append(reconstruct(node, kids))
            continue
        if stopped or not (node.ordinary and matches_root(node, selectors)):
            results.append(node)
            continue
        index = len(attempted)
        cancellation = gate.check(f"before:{index}")
        if cancellation is not None:
            stopped = True
            canceled_by_task = cancellation
            results.append(node)          # never attempted: preserve original exactly
            continue
        attempted.append(node.occurrence)
        result = repair(replace(node, context=path))
        if result is not None and not isinstance(result, Failure):
            raise TypeError("repair must return void or an exception")
        results.append(None if result is None else combine(node, result, site="repair-result"))
        if result is not None and result.canceled:
            stopped = True               # transported callback cancellation is sufficient
            continue
        cancellation = gate.check(f"after:{index}")
        if cancellation is not None:
            stopped = True
            canceled_by_task = cancellation
    result = results[0]
    if not stopped:
        canceled_by_task = gate.check("exit")
    if canceled_by_task is not None:
        result = canceled_by_task if result is None else combine(result, canceled_by_task)
    return result, attempted


def ids(e):
    return [] if e is None else [f.occurrence for f in leaves(e)]


def run_checks():
    partitions = 0
    kinds = ("FileError", "ParseError", "Canceled", "none", "Stop")
    selectors = tuple(frozenset((k,)) for k in kinds + ("error", "exception"))
    for n in (1, 2, 3, 4):
        for ks in product(kinds, repeat=n):
            values = [Failure(k, i, origin=f"line:{i}") for i, k in enumerate(ks)]
            shapes = [join(*values)]
            if n > 1:
                shapes.append(with_context(combine(values[0], join(*values[1:])), "outer"))
            for tree in shapes:
                flat = list(leaves(tree))
                assert [e.kind for e in flat] == list(ks)
                assert [e.origin for e in flat] == [None if k == "none" else f"line:{i}" for i, k in enumerate(ks)]
                assert tree.canceled == ("Canceled" in ks)
                if tree.group:
                    assert not tree.ordinary
                    assert not matches_root(tree, {"Canceled", "FileError", "error"})
                for selected in selectors:
                    yes, no = split(tree, selected)
                    actual = [[x for branch in side for x in leaves(branch)] for side in (yes, no)]
                    expected = [[x for x in flat if matches_root(x, selected)],
                                [x for x in flat if not matches_root(x, selected)]]
                    assert actual == expected
                    partitions += 1
                if tree.canceled:
                    for selected in (None, {"error"}, {"exception"}, {"ErrorGroup"}, {"FileError"}):
                        assert default(tree, selected) == "forward"
                    assert propagate(tree, {"Canceled"}) == "forward"
                if tree.group and tree.canceled:
                    assert default(tree, {"Canceled"}) == "forward"
                    assert default(tree, {"Canceled", "ErrorGroup"}) == "default"
                if tree.group and not tree.canceled:
                    assert propagate(tree, {"Canceled"}) == "retain"
                    assert default(tree, {"ErrorGroup"}) == "default"
    a = Failure("FileError", 1, payload=(("message", "first"),))
    b = Failure("ParseError", 2, payload=(("message", "second"),))
    assert join() is None and join(a) is a
    assert combine(a, b) == join(a, b)
    assert combine(a, b).children == (a, b)
    assert combine(a, b).message == "multiple failures"
    assert [x.message for x in leaves(combine(a, b))] == ["first", "second"]
    assert ids(combine(a, a)) == [1, 1]
    try:
        combine(a, 7)
    except TypeError:
        pass
    else:
        raise AssertionError("successful operand accepted")
    folded = a
    for e in (b, a):
        folded = combine(folded, e)
    assert ids(folded) == [1, 2, 1]
    events = []
    def operand(label, value):
        events.append(label)
        return value
    combine(operand("left", Failure("Canceled", 0)), operand("right", a))
    assert events == ["left", "right"]    # & is eager even with a canceled first operand
    # M1: cancellation before/between/after matches, including nested/contextual/erased inputs.
    missing1, denied, missing2 = Failure("Missing", 10), Failure("Denied", 11), Failure("Missing", 12)
    cancel = Failure("Canceled", 13)
    incoming_cases = 0
    for ordering in permutations((missing1, denied, missing2, cancel)):
        forms = [join(*ordering), with_context(join(*ordering), "batch"),
                 with_context(combine(ordering[0], with_context(join(*ordering[1:]), "nested")), "outer")]
        for original in forms:
            erased = {"exception": original}["exception"]
            calls = []
            gate = Gate()
            out, admitted = recover(erased, {"Missing"}, lambda e: calls.append(e), gate)
            assert out is original
            assert not calls and not admitted and not gate.calls
            assert list(leaves(out)) == list(leaves(original))
            assert propagate(erased, {"Canceled"}) == "forward"  # explicit guard's algebra
            incoming_cases += 1
    normal = with_context(join(missing1, denied, missing2), "assets")
    # Entry, between callbacks, after callbacks, and last-success checks.
    gate_cases = 0
    for point, expected_attempts in [("entry", []), ("before:0", []), ("after:0", [10]),
                                     ("before:1", [10]), ("after:1", [10, 12]), ("exit", [10, 12])]:
        calls = []
        def ok(e):
            calls.append(e.occurrence)
        out, admitted = recover(normal, {"Missing"}, ok, Gate({point}))
        assert calls == admitted == expected_attempts
        retained = [i for i in (10, 11, 12) if i not in admitted]
        assert ids(out) == retained + [-2]
        assert out.canceled
        gate_cases += 1
    # Cancellation returned by a callback, including a group, stops subsequent callbacks.
    for reply in (cancel, with_context(combine(Failure("RepairError", 14), cancel), "repair")):
        out, admitted = recover(normal, {"Missing"}, lambda e: reply, Gate())
        assert admitted == [10]
        assert ids(out) == [10] + ids(reply) + [11, 12]
        assert out.canceled
    # Ordinary repair failures retain the original, but independent repairs continue.
    repair_fail = Failure("RepairError", 14)
    out, admitted = recover(normal, {"Missing"}, lambda e: repair_fail if e.occurrence == 10 else None, Gate())
    assert admitted == [10, 12] and ids(out) == [10, 14, 11]
    assert [f.text for f in list(leaves(out))[0].context] == ["assets"]
    # No matching leaf: unchanged identity. All matched repaired: no failure, not none.
    out, admitted = recover(denied, {"Missing"}, lambda e: None, Gate())
    assert out is denied and not admitted
    out, admitted = recover(combine(missing1, missing2), {"Missing"}, lambda e: None, Gate())
    assert out is None and admitted == [10, 12]
    # Successful callback + task cancellation is still canceled, even for a lone final match.
    out, admitted = recover(missing1, {"Missing"}, lambda e: None, Gate({"after:0"}))
    assert ids(out) == [-2] and admitted == [10]
    # A failure and a simultaneous task cancellation retain all three distinct occurrences.
    out, admitted = recover(missing1, {"Missing"}, lambda e: repair_fail, Gate({"after:0"}))
    assert ids(out) == [10, 14, -2]
    # Two new context calls with identical text remain distinct frames.
    contextual = with_context(with_context(a, "same"), "same")
    assert len(next(leaves(contextual)).context) == 2
    assert a.context == ()
    # Cached cancellation read and iterative walks: no recursive query through the tree.
    deep = cancel
    for _ in range(2000):
        deep = combine(deep, b)
    assert deep.canceled
    assert len(list(leaves(deep))) == 2001
    yes, no = split(deep, {"Canceled"})
    assert ids(yes[0]) == [13] and len(ids(no[0])) == 2000
    return partitions, incoming_cases, gate_cases


if __name__ == "__main__":
    partitions, incoming, gates = run_checks()
    print(f"PASS: {partitions} partitions; {incoming} incoming-cancellation cases; {gates} admission schedules; operator/recovery/context/deep-tree checks")
