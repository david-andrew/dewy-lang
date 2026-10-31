"""A stand-in for the expression dispatcher (checker_expr) in statement-leaf differentials.

Statement leaves call `check_expr` directly; their drivers route it to a stub of their own
so each leaf is compared with its frozen twin alone. The real dispatcher has its own
differential (test_selfhost_checker_expr.py).
"""
from tests.test_selfhost_checker_resolve import compare

DEWY = r'''$runtime_checks
CheckExprDouble:type=[
    check:<(node:int64 expected:int64):>int64>
]
let dbl_host:ptr<CheckExprDouble>=$unsafe (uint64(0) as ptr<CheckExprDouble>)
check_expr_double=(host:ptr<CheckExprDouble>):>int64=>$unsafe {
    dbl_host=host
    0
}
check_expr=(n:int64 expected:int64):>int64=>$unsafe {dbl_host[0].check(n expected)}
'''

JO = r'''struct CheckExprDouble:
    check: (int, int) -> int
dbl_host: *CheckExprDouble
check_expr_double = (host: *CheckExprDouble) -> int:
    dbl_host = host
    0
check_expr = (n: int, expected: int) -> int: dbl_host[0].check(n, expected)
'''

DOUBLES = {'checker_expr': {'dewy': DEWY, 'jo': JO}}


def compare_leaf(compiler, tmp_path, release, driver, stub=None, status=0, extra_stems=()):
    """compare() with checker_expr replaced by the double, bound to the driver's `stub`."""
    if stub is not None:
        head, sep, tail = driver.partition('\nmain = ():')
        assert sep, 'driver has no main'
        driver = (head + f'\ndbl_services = CheckExprDouble({stub})\n'
                  'dbl_bound = check_expr_double(&dbl_services)' + sep + tail)
    return compare(compiler, tmp_path, release, driver, status, extra_stems, DOUBLES)
