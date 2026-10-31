"""The panics call-graph solver (effect_panics) matches its frozen Jo twin."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

STEMS = ('checker_state', 'effect_panics')

DRIVER = r'''
fns: FnInst[] = [FnInst()]
panic_index: int[]
panic_low: int[]
panic_answer: int[]
panic_witness: int[]
panic_via: int[]
panic_local: int[]
panic_local_via: int[]
panic_edge_at: int[]
panic_edge_end: int[]
panic_edges: int[]
panic_stack: int[]
panic_serial = 0
draw_guard = 0
draw_required: bool[]
graph: {int: int[]} = {}
sources: {int: int} = {}
local_sources: {int: int} = {}
library: {int: bool} = {}
events: str[]
scan = (f: int) -> bool:
    events.push("scan:{f}")
    panic_edge_at[f] = panic_edges.len()
    panic_edge_end[f] = panic_edges.len()
    if let w = sources.get(f): panic_witness[f] = w
    if let l = local_sources.get(f): panic_local[f] = l
    loop x in graph.get(f) ?? []: panic_edges.push(x)
    panic_edge_end[f] = panic_edges.len()
    library.has(f)
component = (start: int):
    members: int[]
    loop i in [start..panic_stack.len()): members.push(panic_stack[i])
    events.push("component:{start}:{members}")
opted = (n: int) -> bool:
    events.push("opted:{n}")
    n % 10 == 7
host = EffectPanicHost(scan, component, opted)
input = EffectPanicInput(&fns, &panic_index, &panic_low, &panic_answer, &panic_witness, &panic_via, &panic_local, &panic_local_via, &panic_edge_at, &panic_edge_end, &panic_edges, &panic_stack, &panic_serial, &draw_guard, &draw_required, &host)
binding = effect_panics_bind(&input)
reset = ():
    panic_index = []; panic_low = []; panic_answer = []; panic_witness = []; panic_via = []
    panic_local = []; panic_local_via = []; panic_edge_at = []; panic_edge_end = []; panic_edges = []
    panic_stack = []; panic_serial = 0; events = []
show = ():
    print(panic_answer)
    print(panic_witness)
    print(panic_via)
    print(panic_local)
    print(panic_index)
    print(panic_low)
    print(draw_required.len())
    print(events)
main = ():
    # f1..f12, modules: 1-3 in module 1, 4-5 in modules 2 and 3, the rest 4.
    loop i in [1..13): fns.push(FnInst(mod=i32(if i <= 3: 1 else if i == 4: 2 else if i == 5: 3 else: 4)))
    # A chain to an explicit panic.
    graph[1] = [2, 101]; graph[2] = [3, 102]; sources[3] = 900
    # A cycle across modules whose source is module-local: answer 3 for its
    # own module, 2 for the other one; an opted-in edge (node ...7) stays 3.
    graph[4] = [5, 104, 6, 117]; graph[5] = [4, 105]; local_sources[5] = 905
    graph[6] = [3, 107]
    # A library body stops at its first independent panic.
    graph[7] = [3, 108, 8, 109]; sources[7] = 907; library[7] = true
    graph[8] = [9, 110]; graph[9] = [8, 111, 10, 112]; graph[10] = [11, 113]
    graph[11] = [1, 114, 12, 115]
    loop f in [0..14): print("{f}:{effect_panics(f)}")
    show()
    print(panic_reaches(4, 5), panic_reaches(5, 4), panic_reaches(1, 3), panic_edge_answer(6, 3, 107), panic_edge_answer(1, 2, 101))
    # The draw-context check sees each component; library walks then continue.
    reset()
    draw_guard = 1
    loop f in [11, 9, 4, 12, 7, 2, 1, 3, 5, 6, 8, 10]: print("{f}:{effect_panics(f)}")
    show()
    print("ok")
'''


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_effect_panics_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in STEMS:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in STEMS) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary, *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
    lines = outputs[0].decode().splitlines()
    # The chain panics; the cycle answers per module; the opted-in caller is local.
    assert lines[1:7] == ['1:true', '2:true', '3:true', '4:true', '5:true', '6:true']
    assert 'component:' in outputs[0].decode()
