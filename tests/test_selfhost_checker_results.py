"""Checker result walks and reentrant candidate selection against frozen Jo."""
import random
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
nodes: Node[] = [Node()]
lists: i32[]
files = [SrcFile(is_dewy = true)]
events: int[]
grow = false
lookup_name = (name: int) -> int:
    events.push(name)
    if grow:
        grow = false
        saved = nodes
        loop i in [0..200): nodes.push(Node()); lists.push(0); files.push(SrcFile())
        assert(saved.len() < nodes.len())
        assert(not cr_has_value_return(0))
    if name == 9: 0 else: 1
pending_names = (name: int) -> int[]: [name, 8]
choose = (n: int, need_literal: bool) -> CheckerResultCandidate:
    events.push(n); events.push(if need_literal: 1 else: 0)
    grow = true
    lookup_name(10)
    if nodes[n].kind == .int_lit: return CheckerResultCandidate(if need_literal: 42 else: 0, true)
    if nodes[n].kind == .float_lit: return CheckerResultCandidate(43, false)
    CheckerResultCandidate()
host = CheckerResultHost(lookup_name, pending_names, choose)
binding = checker_results_bind(&nodes, &lists, &files, &host)
make = (kind: NK, a: int = 0, b: int = 0, c: int = 0, name: int = 0, flags: int = 0, children: int[] = []) -> int:
    n = nodes.len()
    nodes.push(Node(kind = kind, a = i32(a), b = i32(b), c = i32(c), name = i32(name), flags = i32(flags), list = i32(lists.len()), nlist = i32(children.len())))
    loop child in children: lists.push(i32(child))
    n
query = (n: int):
    print("{cr_has_value_return(n)}:{cr_has_propagate(n)}:{cr_syntactic_void(n)}:{cr_may_express(n)}:{cr_base_case(n, [7, 8])}")
    leaves: int[]
    cr_value_leaves(n, leaves); print(leaves)
    leaves = []; cr_returned_values(n, leaves); print(leaves)
main = ():
    integer = make(.int_lit)
    floating = make(.float_lit)
    ret = make(.return_, integer)
    propagation = make(.propagate, integer)
    hidden = make(.lambda, ret, propagation)
    loop_node = make(.for_, 0, 0, 2147483647)
    assert(not cr_has_value_return(hidden) and not cr_has_propagate(hidden))
    assert(not cr_has_value_return(loop_node) and not cr_has_propagate(loop_node))
    leaves: int[]
    cr_returned_values(loop_node, leaves); assert(leaves.len() == 0)
    branch = make(.if_, 0, integer)
    cr_value_leaves(branch, leaves); assert(leaves.len() == 0)
    files[0].is_dewy = false
    cr_value_leaves(branch, leaves); assert(leaves == [integer])
    files[0].is_dewy = true
    first = make(.exprstmt, integer)
    second = make(.exprstmt, floating)
    choice = make(.if_, 0, first, second)
    assert(cr_recursive_base_type(choice, 7) == 43)
    choice = make(.if_, 0, first, first)
    assert(cr_recursive_base_type(choice, 7) == 42)
    unresolved = make(.ident, 0, 0, 0, 9)
    pending = make(.ident, 0, 0, 0, 7)
    assert(not cr_base_case(unresolved, []) and not cr_base_case(pending, [7]))
    known = make(.ident, 0, 0, 0, 6)
    grow = true
    assert(cr_base_case(known, []))
    print(events)
'''


def corpus():
    rng = random.Random(2881)
    lines = []
    # Acyclic trees exercise all three child fields and list runs. Nested
    # lambdas, discarded blocks and dialects retain distinct traversal policy.
    kinds = ['int_lit', 'ident', 'return_', 'propagate', 'lambda', 'exprstmt',
             'block', 'if_', 'iflet', 'for_', 'while_', 'loopx', 'match_', 'arm']
    for i in range(90):
        child = lambda: f'r{rng.randrange(i)}' if i and rng.random() < .6 else '0'
        kind = rng.choice(kinds)
        children = ', '.join(child() for _ in range(rng.randrange(3)))
        lines.append(f'    r{i} = make(.{kind}, {child()}, {child()}, {child()}, {rng.randrange(10)}, {rng.choice([0, 8])}, [{children}])')
        lines.append(f'    query(r{i})')
    return '\n'.join(lines) + '\n    print("ok")\n'


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_result_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('node_store', 'source_types', 'checker_results')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER + corpus())
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        assert ran.stdout.endswith(b'ok\n')
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
