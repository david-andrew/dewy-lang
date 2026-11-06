"""Channel occupancy, edge strengthening and first-cycle choice match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf
from tests.test_selfhost_deadlock_waits import JO as WAITS, DRIVER as WAIT_DRIVER

JO = dict(WAITS)
JO['deadlock.jo'] += r'''
struct DcEvent:
    kind: int
    loc: DlLoc
    loops: int[]
    branch: bool
    held: DlLoc[]
    held_sites: int[]
    site: int
struct DcActor:
    events: DcEvent[]
    name: str
    multi: bool
    group: str
    ret: int
struct DcEdge:
    src: str
    dst: str
    certain: bool
    text: str
    site: int
dc_actors: DcActor[]
dc_edges: DcEdge[]
dc_edge_at: {str: int}
dc_precise = true
dc_complete = true
dc_exclusive: {str: bool}
dc_attempts: {str: bool}
dc_cancelable_groups: {str: bool}
dc_ends: {str: bool}
dc_unknown_attempt = false
dc_warned: {int: bool}
collects = 0
dc_collect_double = (): collects += 1
undecided_double = (site: int, msg: str, other: int[]): events.push("undecided:{site}:{msg}:{other}")
'''
JO['util.jo'] += 'err_notes: (int, str)[]\n'
JO['deadlock_channels.dewy'] = r'''from p"deadlock.jo" import (DlLoc dc_cancelable_groups dc_warned dc_split as split_double)
dc_split=(n:int64):>bool=>split_double(n)
dc_capacity=(l:DlLoc):>int64=>l.k
dc_mult=(ev:array<int64> at:array<int64>):>int64=>if ev.length >? 0 {ev[0]} else {1}
dc_may_fail=(t:int64):>bool=>t =? 9
dc_cancelable=(group:string):>bool=>dc_cancelable_groups.has(group)
dc_join_line=(group:string):>string=>" at line 90"
dl_report_warn=(site:int64):>bool=>{
    if dc_warned.has(site) {return false}
    dc_warned[site]=true
    true
}
'''
JO['deadlock_channels.jo'] = r'''use 'deadlock.jo'
dc_capacity = (l: DlLoc) -> int: l.k
dc_mult = (ev: int[], at: int[]) -> int:
    if ev.len() > 0: return ev[0]
    1
dc_may_fail = (t: int) -> bool: t == 9
dc_cancelable = (group: str) -> bool: dc_cancelable_groups.has(group)
dc_join_line = (group: str) -> str: " at line 90"
dl_report_warn = (site: int) -> bool:
    if dc_warned.has(site): return false
    dc_warned[site] = true
    true
'''
JO['deadlock_channel_walk.dewy'] = '''from p"deadlock.jo" import dc_collect_double
dc_collect=():>void=>dc_collect_double()
'''
JO['deadlock_channel_walk.jo'] = "use 'deadlock.jo'\ndc_collect = (): dc_collect_double()\n"
JO['deadlock_waits.dewy'] = '''from p"deadlock.jo" import undecided_double
dl_undecided=(site:int64 msg:string other:array<int64>=[]):>void=>undecided_double(site msg other)
'''
JO['deadlock_waits.jo'] = "use 'deadlock.jo'\ndl_undecided = (site: int, msg: str, other: int[] = []): undecided_double(site, msg, other)\n"

DRIVER = WAIT_DRIVER.split('main = ():')[0] + r'''
event = (kind: int, loc: DlLoc, site: int, times: int = 1, branch: bool = false) -> DcEvent:
    DcEvent(kind, loc, [times], branch, [], [], site)
clear = ():
    dc_actors = []; dc_edges = []; dc_edge_at = {}; events = []; err_notes = []
    dc_precise = true; dc_complete = true; dc_exclusive = {}; dc_attempts = {}
    dc_cancelable_groups = {}; dc_ends = {}; dc_unknown_attempt = false; dc_warned = {}
main = ():
    a = DlLoc(2, node(.vardecl), 1, "", true); nodes[a.id].name = 1
    b = DlLoc(2, node(.vardecl), 1, "", true); nodes[b.id].name = 2
    key = dl_key(a)
    dc_actors = [DcActor([event(1, a, 10), event(1, a, 11)], "main", false, "", 0)]
    assert(dc_send_waits(0, key, 0, true) == 0 and dc_send_waits(0, key, 1, true) == 2)
    assert(dc_send_waits(0, key, 1, false) == 0)
    dc_actors[0].events[1].branch = true; assert(dc_send_waits(0, key, 1, true) == 1)
    dc_actors[0].events[1] = event(2, a, 11); assert(dc_send_waits(0, key, 1, true) == 0)
    dc_actors[0].events[1] = event(7, a, 11, -1); assert(dc_send_waits(0, key, 1, true) == 1)
    dc_actors[0].events = [event(6, a, 10, 3), event(1, a, 11)]
    assert(dc_send_waits(0, key, 1, true) == 1)
    dc_exclusive[key] = true; assert(dc_send_waits(0, key, 1, true) == 2)
    dc_precise = false; assert(dc_send_waits(0, key, 1, true) == 1); dc_precise = true
    dc_actors[0].events = [event(2, a, 10), event(2, a, 11), event(4, a, 12), event(5, a, 13), event(3, a, 14)]
    assert(dc_first_receive(0, 0) and not dc_first_receive(0, 1))
    loop i in [0..5):
        w, text, sure = dc_wait_node(0, i, i, true)
        if i == 1 or i == 4: assert(w == "")
        else: assert(sure == 2 and len(text) > 0)
    dc_attempts[key] = true
    w, text, sure = dc_wait_node(0, 0, 0, true); assert(sure == 1)
    clear()
    dc_add_edge("Ra", "Sb", false, "weak", 10)
    dc_add_edge("Ra", "Sb", true, "strong", 11)
    dc_add_edge("Ra", "Sb", false, "later", 12)
    assert(dc_edges.len() == 1 and dc_edges[0].certain and dc_edges[0].site == 11)
    dc_add_edge("Sb", "Ra", true, "return", 20)
    dc_cycles()
    assert(events.len() == 2 and contains(events[0], "bounded channel cycle: strong; return"))
    assert(err_notes.len() == 1 and err_notes[0].0 == 20)
    clear()
    dc_add_edge("La", "La", true, "locks only", 1); dc_cycles(); assert(events.len() == 0)
    dc_add_edge("Ra", "Ra", false, "self", 2); dc_cycles()
    assert(events.len() == 1 and contains(events[0], "may wait for itself"))
    clear()
    dc_actors = [DcActor([event(2, a, 30)], "reader", false, "group", 9)]
    dc_edges_build()
    assert(dc_cancelable_groups.has("group") and events.len() == 1)
    assert(contains(events[0], "group cancellation may end the wait"))
    clear()
    dc_actors = [DcActor([event(2, a, 40)], "orphan", false, "", 0)]
    dc_edges_build(); assert(events.len() == 2 and contains(events[0], "it waits forever"))
    clear()
    # Each unique producer holds the other queue's drainer until its send completes.
    dc_actors = [DcActor([event(1, a, 50, 2), event(2, b, 51)], "one", false, "g1", 0),
                 DcActor([event(1, b, 60, 2), event(2, a, 61)], "two", false, "g2", 0)]
    dc_edges_build(); assert(dc_exclusive.has(dl_key(a)) and dc_exclusive.has(dl_key(b)))
    assert(dc_edges.len() > 0); dc_cycles(); assert(contains(events[0], "bounded channel cycle"))
    clear()
    fuzzy = a; fuzzy.exact = false
    dc_actors = [DcActor([event(2, fuzzy, 70)], "unknown", false, "", 0)]
    dc_attempts[dl_key(fuzzy)] = true; dc_ends[dl_key(fuzzy)] = true
    dc_analyze(); assert(collects == 1 and events.len() == 1)
    assert(contains(events[0], "owned end may close on drop"))
    print("channel graph ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_deadlock_channel_graph_twins(compiler, tmp_path, release):
    assert compare_leaf(compiler, tmp_path, release, DRIVER,
                        extra_stems=('deadlock_locations', 'deadlock_channel_graph'),
                        jo_doubles=JO) == b'channel graph ok\n'
