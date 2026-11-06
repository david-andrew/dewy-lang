"""Wait diagnostics and demanded atomic walks match frozen Jo with narrow services."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.test_selfhost_deadlock_summaries import JO as SUMMARIES, DRIVER as SUMMARY_DRIVER

JO = dict(SUMMARIES)
JO['ast.jo'] += '''kids = (n: int) -> int[]:
    out: int[]
    loop i in [0..nkids(n)): out.push(kid(n, i))
    out
'''
JO['deadlock.jo'] += 'dl_relevant: {int: bool}\n'
JO['util.jo'] += '''fatal = (site: int, msg: str): events.push("fatal:{site}:{msg}")
warn = (site: int, msg: str): events.push("warn:{site}:{msg}")
'''
JO['directives.jo'] += 'dir_no_deadlocks = (site: int) -> bool: site == 99\n'
JO['expr.jo'] += "use 'ast.jo'\n"
JO['expr.jo'] += 'ntype = (n: int) -> int: int(nodes[n].type)\n'
JO['concurrency.jo'] += 'concurrency_builtin_type = (t: int, name: str) -> bool: t == 7 and name == "Atomic"\n'

DRIVER = SUMMARY_DRIVER.split('main = ():')[0] + r'''
method = (name: int, receiver: int) -> int:
    d = node(.fn_); nodes[d].name = i32(name)
    f = fns.len(); fns.push(FnInst()); fns[f].decl = i32(d)
    c = node(.call, 0, f); children(c, [receiver]); c
main = ():
    globals.resize(3); globals[1].name = 1; globals[2].name = 2
    fns.resize(1)
    a = DlLoc(2, node(.vardecl), 0, "", true); nodes[a.id].name = 1
    b = DlLoc(2, node(.vardecl), 0, "", true); nodes[b.id].name = 2
    p = DlLoc(3, 1, 0, "", true)
    held = [DlHeld(a, 10, 1)]
    dl_cur = dl_summary(0)
    dl_wait(held, p, 20, "", 30)
    assert(events.len() == 0 and dl_cur.edges.len() == 1)
    dl_report = true
    dl_wait(held, a, 20, "helper", 30)
    assert(events.len() == 1 and contains(events[0], "already holds since line 20 (helper, takes it at line 30)"))
    events = []
    fuzzy = a; fuzzy.exact = false
    dl_wait(held, fuzzy, 20, "", 30)
    assert(events.len() == 1 and starts_with(events[0], "warn:30:") and contains(events[0], "may wait"))
    events = []; dl_undecided(30, "unknown", [10, 99])
    assert(events.len() == 2 and starts_with(events[0], "fatal:30:") and starts_with(events[1], "warn:30:"))
    events = []; dir_deadlocks_any = true
    dl_wait(held, dl_unknown(), 99, "outer", 30)
    assert(events.len() == 1 and contains(events[0], "compiler cannot name one of them"))
    events = []; dl_wait(held, b, 99, "", 30)
    assert(events.len() == 0)
    dl_summaries[2] = DlSummary([DlAcq(a, 20, false, "")], {}, [], {}, [], {})
    dl_join(2, held, 30, "tasks"); assert(events.len() == 0)
    dl_relevant[2] = true; dl_join(2, held, 30, "tasks"); assert(events.len() == 0)
    dl_summaries[2] = DlSummary([DlAcq(a, 20, true, ""), DlAcq(fuzzy, 25, true, "")], {}, [], {}, [], {})
    dl_report = false; dl_join(2, held, 30, "tasks"); assert(events.len() == 0)
    dl_report = true; dl_join(2, held, 30, "tasks")
    assert(events.len() == 3 and contains(events[0], "neither can go on") and contains(events[2], "may take the same lock"))
    events = []
    # Atomic queries recurse through scalar children and list children, never lambdas.
    names = ["", "alpha", "beta", "load", "get", "store", "set", "add", "compare_swap", "set_max"]
    recv = node(.ident, 0, 1, int(SK.global)); nodes[recv].type = 7
    recv2 = node(.ident, 0, 2, int(SK.global)); nodes[recv2].type = 7
    read = method(3, recv); other_read = method(4, recv2)
    assert(dl_atomic_name(read, ["load"]) and not dl_atomic_name(read, ["store"]))
    nodes[read].aux = 1; assert(not dl_atomic_name(read, ["load"])); nodes[read].aux = 0
    nodes[recv].type = 0; assert(not dl_atomic_name(read, ["load"])); nodes[recv].type = 7
    noargs = node(.call, 0, 1); assert(not dl_atomic_name(noargs, ["load"]))
    assert(not dl_atomic_name(recv, ["load"]))
    body = node(.block); children(body, [node(.lambda, read), other_read])
    lp = node(.while_, read); nodes[lp].b = i32(body); nodes[lp].pos = 40
    root = node(.block); children(root, [lp, node(.lambda, lp)])
    found: int[]; dl_find_loops(root, found); assert(found == [lp])
    reads: DlLoc[]; dl_atomic_reads(root, 0, reads)
    assert(reads.len() == 2 and reads[0].id == 1 and reads[1].id == 2)
    assert(not dl_atomic_written(root, 0, reads[0]))
    f = fns.len(); fns.push(FnInst()); fns[f].body = i32(root)
    dl_polling(f)
    assert(events.len() == 1 and contains(events[0], "polls 'alpha'"))
    events = []
    loop nm in [5..10):
        write = method(nm, recv)
        assert(dl_atomic_written(write, 0, reads[0]) and not dl_atomic_written(write, 0, reads[1]))
        assert(not dl_atomic_written(node(.lambda, write), 0, reads[0]))
    write = method(5, recv)
    children(body, [write]); dl_polling(f); assert(events.len() == 0)
    children(body, []); children(root, [lp, write]); dl_polling(f)
    assert(events.len() == 2 and contains(events[0], "sibling iteration sets"))
    print("waits ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_deadlock_waits_twins(compiler, tmp_path, release):
    assert compare_leaf(compiler, tmp_path, release, DRIVER,
                        extra_stems=('deadlock_locations', 'deadlock_summaries', 'deadlock_waits'),
                        jo_doubles=JO) == b'waits ok\n'
