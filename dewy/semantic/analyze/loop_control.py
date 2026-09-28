"""Conservative loop control summaries, independent of value facts.

An iteration without fallthrough or a continue targeting its own loop executes
at most once. It still needs ordinary condition/body validation, but no search
for an inductive loop head. Nested loops consume their own continue edges.
"""
from dataclasses import dataclass
from .. import hir


@dataclass(frozen=True)
class Summary:
    normal: bool
    continues: frozenset[int] = frozenset()


def summarize(node, cache):
    cached = cache.get(id(node))
    if cached is not None:
        return cached[1]
    if isinstance(node, (hir.FunctionLiteral, hir.GenericFunction)):
        result = Summary(True)
    elif isinstance(node, hir.Continue):
        result = Summary(False, frozenset({node.loop_levels}))
    elif isinstance(node, hir.Break):
        result = Summary(False)
    elif isinstance(node, hir.Block):
        normal, continues = True, frozenset()
        for item in node.items:
            if not normal:
                break
            part = summarize(item, cache)
            normal = part.normal
            continues |= part.continues
        result = Summary(normal, continues)
    elif isinstance(node, hir.Flow):
        normal, continues = node.default is None, frozenset()
        for arm in node.arms:
            condition = summarize(arm.condition, cache)
            body = summarize(arm.body, cache)
            edges = condition.continues | body.continues
            if isinstance(arm, hir.LoopArm):
                # The inner loop can fall through; its local continues do
                # not return to this loop's condition. Outer targets remain.
                normal = True
                edges = frozenset(level - 1 for level in edges if level > 0)
            else:
                normal |= body.normal
            continues |= edges
        if node.default is not None:
            part = summarize(node.default, cache)
            normal |= part.normal
            continues |= part.continues
        result = Summary(normal, continues)
    else:
        continues = frozenset().union(*(summarize(child, cache).continues for child in hir.children(node)))
        # Conservatively allow other expressions to finish, even if a
        # stronger control analysis could prove that they never return.
        result = Summary(not isinstance(node, hir.Return), continues)
    cache[id(node)] = (node, result)
    return result


def single_pass(body, cache):
    summary = summarize(body, cache)
    return not summary.normal and 0 not in summary.continues
