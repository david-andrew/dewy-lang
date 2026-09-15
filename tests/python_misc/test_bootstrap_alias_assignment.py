"""An alias declaration and an assignment retain distinct syntax identities."""
import test_bootstrap_check as source_values


CASES = [
    'Node:type=[x:int64]\nlet node=Node[42]\nnode.x',
    'Node:type=[x:int64]\nlet read=():>int64=>{let Node=type of [y:int64] return Node[42].y}\nread()',
    'Node:type=[x:int64]\nlet first=():>int64=>Node[20].x\nlet second=():>int64=>Node[22].x\nfirst()+second()',
]
ERRORS = [
    'Node:type=[x:int64]\nNode=type of [y:int64]',
    'Node:type=[x:int64]\nNode=3',
    'Node:type=[x:int64]\nlet update=():>void=>{Node=type of [y:int64]}',
]


def test_native_alias_assignment(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path)
