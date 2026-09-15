"""Record reconstruction preserves constructors, sharing, and replace errors."""
from dataclasses import InitVar, dataclass, field, replace
import importlib
from pathlib import Path

import pytest

from dewy.utils import dataclass_replace


@dataclass(frozen=True, slots=True)
class Record:
    name: str
    values: list[int]
    flag: bool = field(default=False, kw_only=True)


def test_reconstruction_keeps_children_and_observes_current_values():
    source = Record('before', [1])
    source.values.append(2)
    clone = dataclass_replace(source)
    assert clone == replace(source) and clone is not source
    assert clone.values is source.values
    changed = dataclass_replace(source, name='after', flag=True)
    assert changed == replace(source, name='after', flag=True)
    assert source.name == 'before' and not source.flag
    with pytest.raises(TypeError):
        dataclass_replace(source, unknown=1)


def test_constructor_and_post_init_still_run():
    calls = []

    @dataclass
    class Checked:
        value: int

        def __post_init__(self):
            calls.append(self.value)
            if self.value < 0:
                raise ValueError('negative')

    source = Checked(1)
    assert dataclass_replace(source, value=2).value == 2
    with pytest.raises(ValueError, match='negative'):
        dataclass_replace(source, value=-1)
    assert calls == [1, 2, -1]


def test_special_field_rules_use_standard_replacement():
    @dataclass
    class Derived:
        value: int
        factor: InitVar[int]
        product: int = field(init=False)

        def __post_init__(self, factor):
            self.product = self.value * factor

    source = Derived(3, 4)
    assert dataclass_replace(source, factor=5) == replace(source, factor=5)
    for changes in ({}, {'product': 8}):
        with pytest.raises(TypeError):
            dataclass_replace(source, **changes)
    with pytest.raises(TypeError):
        dataclass_replace(object())
    with pytest.raises(TypeError):
        dataclass_replace(Record)


def test_compilation_matches_standard_reconstruction(monkeypatch):
    from dewy.backend.udewy import codegen
    from dewy.reporting import SrcFile

    source = SrcFile(None, '''
Box:type=[text:string values:array<int64>]
let make=(n:int64):>Box=>[text="item {n}" values=[n n+1]]
let main=():>int64=>{
    let box=make(40)
    let saved=box
    loop i in 0..2 {box.values.push(i)}
    let result=if box.values.length >? saved.values.length saved else box
    if result.values.length >? 1 return result.values[1]+1
    return 0
}
''')
    current = codegen(source, debug_locations=False)
    root = Path(__file__).resolve().parents[2] / 'dewy/backend/udewy'
    for path in root.glob('*.py'):
        module = importlib.import_module('dewy.backend.udewy.' + path.stem)
        if getattr(module, 'replace', None) is dataclass_replace:
            monkeypatch.setattr(module, 'replace', replace)
    for name in ('check', 'ty', 'modules'):
        module = importlib.import_module('dewy.semantic.' + name)
        monkeypatch.setattr(module, 'replace', replace)
    assert codegen(source, debug_locations=False) == current
