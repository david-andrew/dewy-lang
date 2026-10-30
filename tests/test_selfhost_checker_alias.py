"""Alias expansion preserves cache/cycle order and nested arena publication."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''
nodes: Node[] = [Node()]
lists: i32[]
events: str[]
depth = 0
nested = 0
grow = true
snapshot: Node[]
resume = (d: int): events.push("resume:{d}")
error = (kind: int, n: int, pos: int, count: int):
    print("error:{kind}:{n}:{pos}:{count}:{depth}")
    exit(17)
atomic = () -> int:
    events.push("atomic")
    42
enter = (d: int, args: int[]) -> CheckerAliasScope:
    assert(nodes[d].aux == 1)
    events.push("enter:{d}:{args}:{depth}")
    saved = depth
    depth += 1
    CheckerAliasScope(saved, d)
leave = (scope: CheckerAliasScope):
    assert(depth == scope.context + 1)
    depth = scope.context
    events.push("leave:{scope.mark}:{depth}")
resolve = (n: int) -> int:
    events.push("resolve:{n}:{depth}")
    if grow:
        grow = false
        snapshot = nodes
        loop i in [0..256): nodes.push(Node()); lists.push(0)
        assert(ca_resolve_alias(nested, [], 50) == 7)
    if nodes[n].kind == .typealias: return ca_resolve_alias(n, [], 60)
    int(nodes[n].ival)
name = (n: int) -> str:
    if n == 1: return "overflow"
    if n == 2: return "wrap"
    if n == 3: return "saturate"
    "other"
policy = (t: int, p: int, pos: int) -> int:
    events.push("policy:{t}:{p}:{pos}")
    t + p
note = (d: int, t: int):
    assert(nodes[d].aux == 0 and int(nodes[d].type) == t)
    events.push("note:{d}:{t}:{depth}")
host = CheckerAliasHost(resume, error, atomic, enter, leave, resolve, name, policy, note)
binding = checker_alias_bind(&nodes, &lists, &host)
node = (kind: NK, a: int = 0, name: int = 0, value: int = 0) -> int:
    n = nodes.len()
    nodes.push(Node(kind=kind, a=i32(a), name=i32(name), ival=value, pos=n))
    n
prepare = ():
    nested = node(.typealias, node(.tname, 0, 0, 7))
main = ():
    prepare()
    body = node(.tname, 0, 0, 10)
    d = node(.typealias, body)
    attr = node(.field, node(.str_lit), 1)
    nodes[int(nodes[attr].a)].sval = 2
    attrs = node(.block)
    nodes[attrs].list = i32(lists.len()); nodes[attrs].nlist = 1; lists.push(i32(attr))
    nodes[d].c = i32(attrs)
    saved = nodes
    assert(ca_resolve_alias(d, [], 40) == 11)
    assert(depth == 0 and saved[d].type == 0 and saved[d].aux == 0)
    assert(snapshot[d].aux == 1 and snapshot[d].type == 0)
    assert(nodes[d].aux == 0 and nodes[d].type == 11 and nodes[nested].type == 7)
    count = events.len()
    assert(ca_resolve_alias(d, [], 41) == 11)
    assert(events.len() == count + 1, "cached aliases still resume deferred refinements")
    generic = node(.typealias, body)
    nodes[generic].nlist2 = 1
    assert(ca_resolve_alias(generic, [123], 42) == 10 and nodes[generic].type == 0)
    assert(ca_resolve_alias(generic, [456], 43) == 10 and nodes[generic].aux == 0)
    order = node(.typealias)
    nodes[order].aux = -7
    assert(ca_resolve_alias(order, [], 44) == 42 and nodes[order].aux == -7)
    count = events.len()
    assert(ca_resolve_alias(order, [], 45) == 42 and events.len() == count + 1)
    print(events)
    print("ok")
'''


def compare(compiler, tmp_path, release, driver, status=0):
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in ('node_store', 'checker_alias'):
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(f"use 'node_store.{extension}'\nuse 'checker_alias.{extension}'\n" + driver)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])], capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == status, ran.stdout + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    return outputs[0]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_checker_alias_twins(compiler, tmp_path, release):  # noqa: F811
    assert compare(compiler, tmp_path, release, DRIVER).endswith(b'ok\n')


@pytest.mark.parametrize('setup,error', [
    ('nodes[d].nlist2 = 1', 1),
    ('nodes[d].a = i32(d)', 2),
    ('nodes[attr].a = 0', 3),
    ('nodes[int(nodes[attr].a)].kind = .int_lit', 3),
    ('nodes[int(nodes[attr].a)].sval = 4', 4),
])
def test_checker_alias_errors(compiler, tmp_path, setup, error):  # noqa: F811
    driver = DRIVER.split('main = ():')[0] + r'''main = ():
    prepare()
    grow = false
    d = node(.typealias, node(.tname, 0, 0, 10))
    attr = node(.field, node(.str_lit), 1)
    nodes[int(nodes[attr].a)].sval = 2
    attrs = node(.block)
    nodes[attrs].list = i32(lists.len()); nodes[attrs].nlist = 1; lists.push(i32(attr))
    nodes[d].c = i32(attrs)
''' + f'    {setup}\n    ca_resolve_alias(d, [], 40)\n    assert(false)\n'
    assert compare(compiler, tmp_path, False, driver, 17).startswith(f'error:{error}:'.encode())
