"""The directive index, cache and code-scope precedence agree with frozen Jo."""

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

pytestmark = pytest.mark.nightly


SERVICES = '''struct DirScope:
    start: int
    end: int
    setting: int
    value: int
    bundle: int = 0
    at: int = 0

dir_scopes: DirScope[]
dir_scopes_gen = 0
dir_index_len = 0
dir_index_gen = 0
dir_index_wide = false
dir_index_file: int[]
dir_index_setting: int[]
dir_index_group_next: int[]
dir_index_head: int[]
dir_index_tail: int[]
dir_index_next: int[]
dir_cache_setting = [-1, -1, -1, -1]
dir_cache_lo = [0, 0, 0, 0]
dir_cache_hi = [0, 0, 0, 0]
dir_cache_best = [0, 0, 0, 0]
dir_code_any = false
dir_code_by_inst: {int: int} = {}
dir_code_names: int[]
dir_code_current = () -> int: dir_code_by_inst.get(1) ?? 0
pos_file = (p: int) -> int: p >> 40

dir_find_scan = (setting: int, p: int, skip: int) -> int:
    best = -1
    loop i in [0..dir_scopes.len()):
        s = dir_scopes[i]
        if i == skip or s.setting != setting or p < s.start or p > s.end: continue
        if best >= 0:
            old = dir_scopes[best]
            if s.start < old.start or s.start == old.start and s.bundle != 0 and old.bundle == 0: continue
        best = i
    best
'''

DRIVER = '''push_scope = (s: DirScope):
    dir_scopes.push(s)
    dir_scopes_gen += 1

main = ():
    start = dir_index_module_start(2)
    end = dir_index_module_end(2)
    assert(dir_index_value(1, start) == -1)
    push_scope(DirScope(start, end, 1, 1))
    push_scope(DirScope(start + 10, start + 20, 1, 0))
    push_scope(DirScope(start + 10, start + 20, 1, 1, 5))
    push_scope(DirScope(start + 7, start + 21, 5, 0))
    loop p in [start + 8, start + 10, start + 11, start + 20, start + 21, end, end + 1]:
        loop name in [1, 5, 9]:
            loop skip in [-1, 1, 3]:
                assert(dir_index_find(name, p, skip) == dir_find_scan(name, p, skip))
    dir_code_any = true
    dir_code_names = [5, 1]
    dir_code_by_inst[1] = 4
    assert(dir_index_code_slot(1) == 1 and dir_index_code_slot(9) == -1)
    assert(dir_index_value(1, start + 9) == 0 and dir_index_value(5, start + 9) == 0)
    assert(dir_index_value(1, start + 12) == 0)
    dir_scopes = [dir_scopes[0]]
    dir_scopes_gen += 1
    assert(dir_index_find(1, start + 12, -1) == 0)
    push_scope(DirScope(end - 3, end + 3, 5, 1))
    assert(dir_index_find(5, end + 1, -1) == 1 and dir_index_wide)
    assert(dir_index_find(5, end + 1, 1) == -1)
    print("ok")
'''


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_directive_index_twins(compiler, tmp_path, release):
    assert compare_narrow(compiler, tmp_path, release, ('directive_index',), DRIVER,
                          doubles={'services.jo': SERVICES},
                          services=('directive_code', 'directive_rules', 'directives', 'util')) == b'ok\n'
