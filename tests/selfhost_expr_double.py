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


def compare_leaf(compiler, tmp_path, release, driver, stub=None, status=0, extra_stems=(), jo_doubles=None):
    """compare() with checker_expr replaced by the double, bound to the driver's `stub`."""
    if stub is not None:
        head, sep, tail = driver.partition('\nmain = ():')
        assert sep, 'driver has no main'
        driver = (head + f'\ndbl_services = CheckExprDouble({stub})\n'
                  'dbl_bound = check_expr_double(&dbl_services)' + sep + tail)
    return compare(compiler, tmp_path, release, driver, status, extra_stems, DOUBLES, jo_doubles)


def jo_doubles(*tables):
    """Jo-module doubles {file: text} from {file: {name: definition}} tables; the first definition wins."""
    merged = {}
    for table in tables:
        for name, functions in table.items():
            for function, line in functions.items():
                merged.setdefault(name, {}).setdefault(function, line)
    # (a `use` entry, keyed by its module, brings a type a double's signature names)
    return {name: "use 'driver.jo'\n" + ''.join(line + '\n' for line in sorted(functions.values(), key=lambda line: not line.startswith('use ')))
            for name, functions in merged.items()}


def isolate_sinks(modules):
    """Keep callers' sink stubs when the implementation lives in its own leaf."""
    _isolate_services(modules, "checker_sinks", {
        'sink_pack_call': ('n:int64', 'n', 'void'),
        'sink_values_use': ('n:int64 t:int64', 'n t', 'void'),
        'sink_close': ('b:int64 result:int64', 'b result', 'int64'),
        'pack_written': ('f:int64 tn:int64', 'f tn', 'void'),
    })


def _isolate_services(modules, stem, signatures):
    import re
    text = modules.get('check.jo', '')
    dewy, jo = [], ["use 'check.jo'\n"]
    for name, (params, args, result) in signatures.items():
        pattern = r'(?m)^' + name + r' = (\([^\n]*?\)(?: -> [^:\n]+)?):'
        match = re.search(pattern, text)
        if match is None:
            continue
        service = name + '_double'
        text = re.sub(r'(?m)^' + name + r' = ', service + ' = ', text)
        dewy.append(f'from p"check.jo" import {service}\n'
                    f'{name}=({params}):>{result}=>{service}({args})\n')
        jo.append(f'{name} = {match[1]}: {service}({args.replace(" ", ", ")})\n')
    if dewy:
        modules['check.jo'] = text
        modules[stem + '.dewy'] = '$runtime_checks\n' + ''.join(dewy)
        modules[stem + '.jo'] = ''.join(jo)


def isolate_hooks(modules):
    """Keep each caller's hook behavior separate from the hook leaf differential."""
    _isolate_services(modules, 'checker_hooks', {
        'block_sibling': ('n:int64 m:int64 code:int64', 'n m code', 'void'),
        'assign_begin': ('s:int64 code:int64', 's code', 'int64'),
        'decl_annotated': ('s:int64 t:int64 member:int64', 's t member', 'void'),
        'decl_sibling': ('s:int64 t:int64 code:int64', 's t code', 'int64'),
        'decl_literal': ('s:int64', 's', 'int64'),
        'decl_after': ('s:int64 l:int64 t:int64 code:int64', 's l t code', 'void'),
    })
