"""Callable labels preserve byte spellings, source dialect, and reentrant interning."""
import subprocess

import pytest

from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''

names: str[]
nodes: Node[]
lists: i32[]
files: SrcFile[]
events: str[]
grow_enabled = false
grew = false
intern_name = (text: str) -> int:
    events.push(text)
    if grow_enabled and not grew:
        grew = true
        loop i in [0..256):
            names.push("padding:{i}")
            nodes.push(Node())
            lists.push(0)
            files.push(SrcFile())
        assert(tn_label_key([0, 1, 2]) == 0)
    loop i in [0..names.len()):
        if names[i] == text: return i
    names.push(text)
    names.len() - 1
input = TypeLabelInput(&names, &nodes, &lists, &files, intern_name)
binding = type_label_bind(&input)
main = ():
    names = ["", "_", "$hidden", "left", "右", "x", "\nright\n"]
    files = [SrcFile(is_dewy=false), SrcFile(is_dewy=true)]
    nodes = [Node(), Node(pos=1 << 40, list=1, nlist=4), Node(name=3), Node(name=1), Node(name=4), Node(name=2), Node(pos=0, list=1, nlist=4)]
    lists = [0, 2, 3, 4, 5]
    assert(tn_decl_labels(0) == 0)
    assert(tn_decl_labels(6) == 0)
    assert(tn_label_key([]) == 0 and tn_label_key([0, 1, 2]) == 0)
    assert(tn_label_names(0, 3) == [0, 0, 0])
    assert(tn_label_names(0, 0) == [])
    saved_names = names
    saved_nodes = nodes
    saved_lists = lists
    saved_files = files
    grow_enabled = true
    key = int(tn_decl_labels(1))
    assert(grew and names[key] == "left\n\n右\n")
    assert(tn_label_names(key, 99) == [3, 0, 4, 0])
    assert(tn_label_names(key, 0) == [3, 0, 4, 0])
    assert(tn_label_names(6, 0) == [0, intern_name("right"), 0])
    assert(saved_names.len() == 7 and saved_nodes.len() == 7)
    assert(saved_lists.len() == 5 and saved_files.len() == 2)
    grew = false
    decoded = tn_label_names(key, 1)
    assert(grew and decoded == [3, 0, 4, 0])
    assert(tn_label_key(decoded) == key)
    print(events)
    names[3] = "changed"
    assert(saved_names[3] == "left")
    type_label_bind(&input)
    assert(tn_decl_labels(1) != key)
    print("ok")

'''

@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_type_label_twins(compiler, tmp_path, release):  # noqa: F811
    outputs = []
    stems = ('node_store', 'source_types', 'type_labels')
    for extension in ('dewy', 'jo'):
        directory = tmp_path / extension
        directory.mkdir()
        for stem in stems:
            text = (ROOT / f'compiler/{stem}.{extension}').read_text()
            if extension == 'jo':
                text = text.replace(".dewy'", ".jo'")
            (directory / f'{stem}.{extension}').write_text(text)
        source, binary = directory / 'driver.jo', directory / 'driver'
        source.write_text(''.join(f"use '{s}.{extension}'\n" for s in stems) + DRIVER)
        built = subprocess.run([compiler, 'build', source, '-o', binary,
                                *(['--release'] if release else [])],
                               capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([binary], capture_output=True, timeout=60)
        assert ran.returncode == 0, ran.stdout[-3000:] + ran.stderr
        outputs.append(ran.stdout)
    assert outputs[0] == outputs[1]
    assert outputs[0].endswith(b'ok\n')
