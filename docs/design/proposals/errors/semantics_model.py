"""Small executable oracle for this proposal, not a Dewy interpreter or runtime.
No I/O, allocation, ABI, concurrency or ownership guarantee is modeled.
"""
from dataclasses import dataclass, replace
from itertools import product

@dataclass(frozen=True)
class Failure:
    kind: str
    occurrence: int
    children: tuple = ()
    context: tuple = ()
    origin: str = "constructed"
    cause: object = None

    @property
    def ordinary(self):
        return self.kind not in ("Canceled", "none", "Stop", "ExceptionGroup")

    @property
    def canceled(self):
        return self.kind == "Canceled" or any(c.canceled for c in self.children)

    @property
    def group(self):
        return self.kind in ("ErrorGroup", "ExceptionGroup")


def group(children, *, source=None):
    assert children
    kind = "ErrorGroup" if all(c.ordinary for c in children) else "ExceptionGroup"
    if source is None:
        return Failure(kind, -1, tuple(children), origin="join")
    return replace(source, kind=kind, children=tuple(children))


def join(*xs):
    if not xs:
        return None  # model's success-void; not the Failure(kind='none') value
    if len(xs) == 1:
        return xs[0]
    return group(xs)


def context(e, label):
    return replace(e, context=(label,) + e.context)


def caused_by(e, cause):
    if e.group or not e.ordinary or not cause.ordinary:
        raise TypeError("a nongroup error may wrap only an ordinary error cause")
    return replace(e, cause=cause)


def leaves(e):
    pending = [(e, ())]
    while pending:
        item, ancestors = pending.pop()
        if item.group:
            path = ancestors + item.context
            pending.extend((c, path) for c in reversed(item.children))
        else:
            yield replace(item, context=ancestors + item.context)


def root_matches(e, selectors):
    return (e.kind in selectors or "exception" in selectors
            or ("error" in selectors and e.ordinary))


def propagate(e, selectors=None):
    if selectors is None or root_matches(e, selectors):
        return "forward"
    if "Canceled" in selectors and e.canceled:
        return "forward"
    return "retain"


def default(e, selectors=None):
    selected = selectors is None or root_matches(e, selectors)
    canceled_named = selectors is not None and "Canceled" in selectors
    if e.canceled and not (selected and canceled_named):
        return "forward"
    return "default" if selected else "retain"


def split(e, selectors):
    if selectors & {"ErrorGroup", "ExceptionGroup"}:
        raise TypeError("split selectors test leaves only")
    # Postorder with explicit stack; each stack slot denotes an occurrence, not identity.
    stack, values = [(e, False)], []
    while stack:
        item, visited = stack.pop()
        if not item.group:
            values.append((item, None) if root_matches(item, selectors) else (None, item))
        elif not visited:
            stack.append((item, True))
            stack.extend((c, False) for c in reversed(item.children))
        else:
            count = len(item.children)
            outputs = values[-count:]
            del values[-count:]
            sides = []
            for side in (0, 1):
                kids = [v[side] for v in outputs if v[side] is not None]
                if not kids:
                    sides.append(None)
                elif len(kids) == count and all(k is c for k, c in zip(kids, item.children)):
                    sides.append(item)
                else:
                    sides.append(group(kids, source=item))
            values.append(tuple(sides))
    yes, no = values[0]
    return ([] if yes is None else [yes], [] if no is None else [no])


def run_checks():
    checked = 0
    kinds = ("FileError", "ParseError", "Canceled", "none", "Stop")
    selectors = (frozenset((k,)) for k in kinds + ("error", "exception"))
    selectors = tuple(selectors)
    for n in (1, 2, 3, 4):
        for ks in product(kinds, repeat=n):
            xs = [Failure(k, i, origin=f"line:{i}") for i, k in enumerate(ks)]
            shapes = [join(*xs)]
            if n > 1:
                shapes.append(context(join(xs[0], join(*xs[1:])), "outer"))
            for tree in shapes:
                flat = list(leaves(tree))
                assert [f.kind for f in flat] == list(ks)
                assert [f.origin for f in flat] == [f"line:{i}" for i in range(n)]
                assert tree.canceled == ("Canceled" in ks)
                assert not (tree.canceled and tree.ordinary)
                for sel in selectors:
                    yes, no = split(tree, sel)
                    got_yes = [f for r in yes for f in leaves(r)]
                    got_no = [f for r in no for f in leaves(r)]
                    expect_yes = [f for f in flat if root_matches(f, sel)]
                    expect_no = [f for f in flat if not root_matches(f, sel)]
                    assert got_yes == expect_yes, (ks, sel, got_yes, expect_yes)
                    assert got_no == expect_no, (ks, sel, got_no, expect_no)
                    checked += 1
                for sel in (None, {"error"}, {"exception"}, {"ExceptionGroup"}, {"FileError"}):
                    if tree.canceled:
                        assert default(tree, sel) == "forward"
                        assert propagate(tree, {"Canceled"}) == "forward"
                if tree.group and tree.canceled:
                    assert default(tree, {"Canceled"}) == "forward"
                    assert default(tree, {"Canceled", "ExceptionGroup"}) == "default"
                    assert not root_matches(tree, {"Canceled"})
                    assert not root_matches(tree, {"FileError"})
    a = Failure("FileError", 1)
    b = Failure("ParseError", 2)
    assert join() is None and join(a) is a
    assert [x.occurrence for x in leaves(join(a, a))] == [1, 1]
    assert join(Failure("none", 3), a).kind == "ExceptionGroup"
    wrapped = caused_by(Failure("ConfigError", 4), a)
    yes, no = split(wrapped, {"FileError"})
    assert not yes and no == [wrapped]  # cause is not a simultaneous failure
    for outer, cause in ((a, Failure("Canceled", 5)), (join(a, b), a)):
        try:
            caused_by(outer, cause)
        except TypeError:
            pass
        else:
            raise AssertionError("unsafe/duplicable cause accepted")
    nested = context(join(context(a, "inner"), b), "outer")
    assert [x.context for x in leaves(nested)] == [("outer", "inner"), ("outer",)]
    assert a.context == ()
    # Deep aggregate traversal and split do not rely on recursive Python calls.
    deep = a
    for i in range(2000):
        deep = group((deep, b))
    assert len(list(leaves(deep))) == 2001
    yes, no = split(deep, {"FileError"})
    assert len(list(leaves(yes[0]))) == 1
    assert len(list(leaves(no[0]))) == 2000
    # Recovery cancellation must retain matched leaves not yet attempted.
    original = context(join(Failure("Missing", 10), Failure("Denied", 11),
                            Failure("Missing", 12)), "assets")
    matched, rest = split(original, {"Missing"})
    pending, attempted, stopped = list(rest), [], False
    for branch in matched:
        for leaf in leaves(branch):
            if stopped:
                pending.append(leaf)
            else:
                attempted.append(leaf.occurrence)
                pending.append(join(leaf, Failure("Canceled", 13)))
                stopped = True
    recovered = list(leaves(join(*pending)))
    assert attempted == [10]
    assert [f.occurrence for f in recovered] == [11, 10, 13, 12]
    assert [f.context for f in recovered if f.kind != "Canceled"] == [("assets",)] * 3
    return checked


if __name__ == "__main__":
    print(f"PASS: {run_checks()} partition cases plus selection, origin, cause and deep-tree checks")
