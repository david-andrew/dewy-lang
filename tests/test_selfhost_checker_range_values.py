"""A range as a value: its loop-built array desugaring matches frozen Jo node for node."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xn_count = 4
xn_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{nodes.len()}")
    T_STR
xn_error_host = (n: int):
    print("error:{n}:1")
    exit(19)
xn_services = CheckerRangeValueHost(intern_text, xn_check_host, xn_error_host)
xn_inputs = CheckerRangeValueInput(&nodes, &lists, &xn_count, &T_INT, &xn_services)
xn_binding = checker_range_values_bind(&xn_inputs)
dump = (from: int):
    loop i in [from..nodes.len()):
        x = nodes[i]
        print("{i}:{int(x.kind)}:{x.a}:{x.b}:{x.aux}:{x.ival}:{x.name}:{x.pos}:{x.list}:{x.nlist}")
'''

MAIN = r'''
main = ():
    prepare()
    lo = node(.int_lit, 0, 1); hi = node(.int_lit, 0, 5)
    r = node(.range, lo); nodes[r].b = i32(hi); nodes[r].pos = 77
    start = nodes.len()
    print(xn_check(r, T_INT))
    dump(start)
    print("{int(nodes[r].kind)}:{nodes[r].list}:{nodes[r].nlist}:{xn_count}")
    print(lists)
    print(names)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_range_values_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_range_values',)).endswith(b'ok\n')


def test_checker_range_values_open_end(compiler, tmp_path):  # noqa: F811
    main = '''
main = ():
    prepare()
    r = node(.range, node(.int_lit))
    xn_check(r, 0)
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19,
                     extra_stems=('checker_range_values',))
    assert output.rstrip().endswith(b':1')
