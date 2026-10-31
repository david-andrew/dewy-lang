"""`x in a..b`: the bound tests built from it match frozen Jo node for node."""
import pytest

from tests.support import compiler  # noqa: F401
from tests.test_selfhost_checker_resolve import DRIVER as RESOLVER, compare

DRIVER = RESOLVER.split('main = ():')[0] + r'''
xy_count = 2
xy_check_host = (n: int, expected: int) -> int:
    events.push("check:{n}:{expected}:{nodes.len()}")
    T_BOOL
xy_check_to_host = (n: int, t: int) -> int:
    events.push("check-to:{n}:{t}")
    t
xy_capture_host = (n: int, t: int, statements: mut int[]) -> int:
    d = node(.vardecl, n); statements.push(d)
    v = node(.ident); nodes[v].sym = i32(d)
    events.push("capture:{n}:{t}:{d}:{v}")
    v
xy_error_host = (n: int):
    print("error:{n}:1")
    exit(19)
xy_services = CheckerInRangeHost(intern_text, xy_check_host, xy_check_to_host, xy_capture_host, xy_error_host)
xy_inputs = CheckerInRangeInput(&nodes, &lists, &files, &xy_count, &T_INT, &T_BOOL, &xy_services)
xy_binding = checker_in_range_bind(&xy_inputs)
DEWY = 1 << 40
dump = (from: int):
    loop i in [from..nodes.len()):
        x = nodes[i]
        print("{i}:{int(x.kind)}:{x.op}:{x.a}:{x.b}:{x.ival}:{x.name}:{x.type}:{x.aux}:{x.flags}:{x.list}:{x.nlist}")
membership = (needle: int, lo: int, hi: int, inclusive: bool, dewy: bool) -> int:
    r = node(.range, lo); nodes[r].b = i32(hi)
    if inclusive: nodes[r].flags = i32(2)
    n = node(.binary, needle); nodes[n].b = i32(r)
    if dewy: nodes[n].pos = DEWY + n
    n
run = (n: int):
    start = nodes.len()
    print(xy_check(n, 0))
    dump(start)
    print("{int(nodes[n].kind)}:{nodes[n].list}:{nodes[n].nlist}:{nodes[n].type}:{xy_count}")
prepare_in_range = ():
    prepare()
    files.push(SrcFile(is_dewy = true))
'''

MAIN = r'''
main = ():
    prepare_in_range()
    x = node(.ident); nodes[x].name = 2
    run(membership(x, node(.int_lit), node(.int_lit), false, false))
    run(membership(node(.call), node(.int_lit), node(.int_lit), true, false))
    run(membership(node(.int_lit), 0, node(.int_lit), false, false))
    run(membership(node(.call), node(.int_lit), 0, false, false))
    run(membership(node(.ident), node(.int_lit), node(.int_lit), true, true))
    run(membership(node(.ident), 0, node(.int_lit), false, true))
    run(membership(node(.ident), node(.int_lit), 0, false, true))
    run(membership(node(.ident), 0, 0, false, true))
    print(lists)
    print(names)
    print(events)
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_in_range_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER + MAIN,
                   extra_stems=('checker_in_range',)).endswith(b'ok\n')


def test_checker_in_range_unbounded(compiler, tmp_path):  # noqa: F811
    main = '''
main = ():
    prepare_in_range()
    run(membership(node(.int_lit), 0, 0, false, false))
    print("unreachable")
'''
    output = compare(compiler, tmp_path, False, DRIVER + main, status=19, extra_stems=('checker_in_range',))
    assert output.rstrip().endswith(b':1')
