"""Tagged getters may lend stable storage without changing ordinary returns."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_scalar_projection import execute

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/union_getter_borrows.dewy'
PREFIX = FIXTURE.read_text().split('measure=')[0]
CASES = [
    PREFIX + '''save=(nodes:array<Node>):>Node=>{
    const node=forward(nodes 0)
    return node
}
main=():>int64=>{
    let nodes:array<Node>=[Left[21 [21]]]
    let saved=save(nodes)
    nodes.clear
    if saved is? Left and saved.data.length>?0 return saved.value+saved.data[0]
    return 1
}''',
    PREFIX + '''consume=(nodes:array<Node>):>int64=>{nodes.clear return 0}
make=():>array<Node>=>[Left[42 [1]]]
main=():>int64=>{
    let nodes=make()
    const node=forward(nodes 0)
    let ignored=consume(nodes)
    return if node is? Left node.value else 1
}''',
    PREFIX + '''main=():>int64=>{
    let nodes:array<Node>=[Left[42 [1]]]
    const node=forward(nodes 0)
    nodes.clear
    return if node is? Left node.value else 1
}''',
    PREFIX + '''main=():>int64=>{
    let nodes:array<Node>=[Left[42 [1]]]
    let node=forward(nodes 0)
    if node is? Left and node.data.length>?0 {node.data[0]=99}
    const original=forward(nodes 0)
    if original is? Left and original.data.length>?0 and original.data[0]=?1 return original.value
    return 1
}''',
    PREFIX.replace('read=(nodes:', 'let visits:int64=0\nread=(nodes:').replace(
        '    return nodes[id]', '    visits+=1\n    return nodes[id]') + '''main=():>int64=>{
    let nodes:array<Node>=[Left[40 []]]
    const first=forward(nodes 0)
    const second=forward(nodes 0)
    return if first is? Left and second is? Left first.value+visits else 1
}''',
    PREFIX + '''main=():>int64=>{
    let nodes:array<Node>=[none]
    const node=forward(nodes 0)
    return if node is? none 42 else 1
}''',
]


@pytest.mark.parametrize('source', [FIXTURE.read_text(), *CASES])
def test_tagged_getter_value_semantics(tmp_path, source):
    execute(tmp_path, 'union-getter', codegen(SrcFile(None, source), debug_locations=False))


def test_native_tagged_getter_value_semantics(tmp_path):
    from test_bootstrap_structural_text import build_program_driver, check_structural_text
    check_structural_text(build_program_driver(tmp_path), tmp_path, cases=CASES, errors=[])


def test_native_tagged_getter_borrows_allocate_nothing(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    compiled = subprocess.run([build_program_driver(tmp_path), FIXTURE, ROOT / 'library',
                               tmp_path / 'prelude'], capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    for result in execute(tmp_path, 'borrowed-union-getter', compiled.stdout):
        assert result.stdout == '0\n'


def test_native_tagged_getter_preserves_runtime_guard(tmp_path):
    from test_bootstrap_structural_text import build_program_driver
    source = PREFIX + '''main=():>int64=>{
    let nodes:array<Node>=[]
    const node=forward(nodes 0)
    return if node is? Left node.value else 1
}'''
    path = tmp_path / 'guard.dewy'
    path.write_text(source)
    compiled = subprocess.run([build_program_driver(tmp_path), path, ROOT / 'library',
                               tmp_path / 'prelude'], capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    for name, code in [('native', compiled.stdout),
                       ('hosted', codegen(SrcFile(None, source), debug_locations=False))]:
        for result in execute(tmp_path, name, code, 101):
            assert 'assertion' in result.stderr.lower()
