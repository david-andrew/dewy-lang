"""Summary deduplication, reporting and borrowed held-lock state match frozen Jo."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.selfhost_expr_double import compare_leaf, jo_doubles
from tests.test_selfhost_deadlock_locations import JO as LOCATIONS, DRIVER as LOC_DRIVER

JO = dict(LOCATIONS)
JO.update(jo_doubles({'deadlock.jo': {
    'locations': LOCATIONS['deadlock.jo'],
    'DlAcq': '''struct DlAcq:
    loc: DlLoc
    site: int
    wait: bool
    via: str''',
    'DlHeld': '''struct DlHeld:
    loc: DlLoc
    site: int
    guard: int''',
    'DlCallback': '''struct DlCallback:
    param: int
    held: DlLoc[]
    sites: int[]
    site: int''',
    'DlSummary': '''struct DlSummary:
    acqs: DlAcq[]
    acq_keys: {str: bool}
    edges: DlEdge[]
    edge_keys: {str: bool}
    callbacks: DlCallback[]
    cb_keys: {str: bool}''',
    'dl_cur': 'dl_cur: DlSummary',
    'dl_changed': 'dl_changed = false',
    'dl_report': 'dl_report = false',
    'dl_global_keys': 'dl_global_keys: {str: bool}',
    'dl_global_edges': 'dl_global_edges: DlEdge[]',
    'dl_summaries': 'dl_summaries: {int: DlSummary}',
}}))

DRIVER = LOC_DRIVER.split('main = ():')[0] + r'''
main = ():
    a = DlLoc(2, 1, 0, "", true)
    b = DlLoc(2, 2, 0, "", true)
    p = DlLoc(3, 7, 0, "", true)
    unknown = dl_unknown()
    empty = dl_summary(9)
    assert(empty.acqs.len() == 0 and empty.edges.len() == 0 and empty.callbacks.len() == 0)
    assert(not dl_summaries.has(9))
    dl_cur = empty
    dl_add_acq(DlAcq(a, 10, true, "first"))
    assert(dl_changed and dl_cur.acqs.len() == 1)
    dl_changed = false
    dl_add_acq(DlAcq(a, 20, true, "later"))
    assert(not dl_changed and dl_cur.acqs.len() == 1 and dl_cur.acqs[0].site == 10)
    assert(dl_cur.acqs[0].via == "first")
    dl_add_acq(DlAcq(a, 30, false, "held"))
    dl_add_acq(DlAcq(unknown, 40, true, "unknown"))
    assert(dl_changed and dl_cur.acqs.len() == 3)
    dl_changed = false
    dl_add_edge(DlEdge(a, b, 10, 20, "ignored"))
    assert(not dl_changed and dl_global_edges.len() == 0 and dl_cur.edges.len() == 0)
    dl_add_edge(DlEdge(p, b, 11, 21, "symbolic"))
    assert(dl_changed and dl_cur.edges.len() == 1)
    dl_changed = false
    dl_add_edge(DlEdge(p, b, 99, 99, "duplicate"))
    assert(not dl_changed and dl_cur.edges[0].held_site == 11)
    dl_add_edge(DlEdge(b, p, 12, 22, "reverse"))
    assert(dl_changed and dl_cur.edges.len() == 2)
    dl_report = true; dl_changed = false
    dl_add_edge(DlEdge(a, b, 13, 23, "concrete", 50))
    dl_add_edge(DlEdge(a, b, 99, 99, "duplicate", 60))
    dl_add_edge(DlEdge(unknown, b, 0, 0, "unknown"))
    dl_add_edge(DlEdge(a, unknown, 0, 0, "unknown"))
    assert(not dl_changed and dl_global_edges.len() == 1)
    assert(dl_global_edges[0].held_site == 13 and dl_global_edges[0].at == 50)
    dl_add_edge(DlEdge(b, a, 14, 24, "reverse"))
    assert(dl_global_edges.len() == 2)
    dl_cur.callbacks.push(DlCallback(1, [a], [10], 70)); dl_cur.cb_keys["cb"] = true
    dl_summaries[7] = dl_cur
    saved = dl_summary(7)
    assert(saved.acqs.len() == 3 and saved.edges.len() == 2 and saved.callbacks[0].site == 70)
    saved.acqs.pop(); saved.acq_keys.remove(dl_key(a) + "w"); saved.callbacks[0].sites.push(80)
    again = dl_summary(7)
    assert(again.acqs.len() == 3 and again.acq_keys.has(dl_key(a) + "w"))
    assert(again.callbacks[0].sites.len() == 1)
    held = [DlHeld(a, 10, 1), DlHeld(b, 20, 2), DlHeld(p, 30, 3)]
    snapshot = held
    dl_drop(held, 4); assert(held.len() == 3)
    dl_drop(held, 3); assert(held.len() == 3)
    dl_drop(held, 1); assert(held.len() == 1 and held[0].guard == 1 and snapshot.len() == 3)
    dl_drop(held, 0); dl_drop(held, 0); assert(held.len() == 0)
    print("summaries ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_deadlock_summaries_twins(compiler, tmp_path, release):
    assert compare_leaf(compiler, tmp_path, release, DRIVER,
                        extra_stems=('deadlock_locations', 'deadlock_summaries'),
                        jo_doubles=JO) == b'summaries ok\n'
