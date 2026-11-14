"""Warning replay/collection, deferred/fused/IDE routes and deduplication match frozen Jo."""
import pytest
from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

SERVICES = r'''err_held: (int, str)[]
errors_only = false
shown_warnings: str[]
warned: {str: bool}
pc_prechecking = false
pc_collect = false
pc_reordered = false
pc_warn_pos: int[]
pc_warn_text: str[]
dc_lazy_used = false
dc_warning_pos: int[]
dc_warning_text: str[]
fused_on = false
ide_on = false
dc_replay = (): print("replay")
fz_note_text = (kind: int, pos: int, msg: str): print("fused:{kind}:{pos}:{msg}")
ide_warn = (pos: int, msg: str): print("ide:{pos}:{msg}")
pos_str = (p: int) -> str: "p{p}"
'''
DRIVER = r'''main = ():
    err_held = [(1, "pending")]; warn(1, "hidden"); assert(warned.len() == 0)
    err_held = []; pc_prechecking = true; pc_collect = true
    warn(2, "collected"); assert(pc_warn_pos == [2] and pc_warn_text == ["collected"])
    pc_prechecking = false; pc_collect = false; dc_lazy_used = true
    warn(3, "lazy"); dc_lazy_used = false; pc_reordered = true; warn(4, "reordered")
    assert(dc_warning_pos == [3, 4] and dc_warning_text == ["lazy", "reordered"])
    pc_reordered = false; fused_on = true; warn(5, "fused")
    fused_on = false; ide_on = true; warn(6, "ide"); ide_on = false
    warn(7, "shown"); warn(7, "shown"); warn(-1, "é")
    assert(warned.len() == 2 and shown_warnings == ["w7.5", "w-1.2"])
    errors_only = true; shown_warnings.push("w8.5"); warn(8, "prior")
    assert(warned.len() == 3 and shown_warnings.len() == 3)
    print("ok")
'''

@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_source_warnings_twins(compiler, tmp_path, release):
    out = compare_narrow(compiler, tmp_path, release, ('source_warnings',), DRIVER,
                         doubles={'services.jo': SERVICES},
                         services=('util', 'source_queries', 'pcheck', 'lazy_bodies', 'lazy_force',
                                   'fused', 'fused_ops', 'ide', 'ide_ops'))
    assert out == b'replay\nfused:5:5:fused\nide:6:ide\nok\n'
