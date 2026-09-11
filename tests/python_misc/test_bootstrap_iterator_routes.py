"""Iteration excludes overlapping storage writes, preserving sibling fields."""
import pytest
import test_bootstrap_check as source_values

from dewy.reporting import SrcFile
from dewy.semantic import check
from dewy.semantic.errors import UserError

STATE = 'State:type=[input:set<int64> output:set<int64>]\n'
CASES = [
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.output.add(value)}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.output=set[42]}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.output.clear}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {let deferred=():>void=>state.input.clear}}',
    STATE + 'Box:type=[state:State]\nlet scan=(box:Box):>void=>{loop value in box.state.input {box.state.output.add(value)}}',
    'State:type=[input:dict<string int64> output:dict<string int64>]\nlet scan=(state:State):>void=>{loop [key value] in state.input {state.output[key]=value}}',
    'State:type=[input:dict<string int64> output:int64]\nlet scan=(state:State):>void=>{loop [key value] in state.input {state.output+=value}}',
]
ERRORS = [
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.input.add(value)}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.input.clear}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state.input=set[42]}}',
    STATE + 'let scan=(state:State):>void=>{loop value in state.input {state=State[set[] set[]]}}',
    STATE + 'let clear=(@values:set<int64>):>void=>values.clear\nlet scan=(state:State):>void=>{loop value in state.input {clear(@state.input)}}',
    STATE + 'Box:type=[state:State]\nlet scan=(box:Box):>void=>{loop value in box.state.input {box.state=State[set[] set[]]}}',
    'State:type=[input:dict<string int64>]\nlet scan=(state:State):>void=>{loop [key value] in state.input {state.input[key]+=value}}',
    'let scan=(bags:array<set<int64> length=2>):>void=>{loop value in bags[0] {bags[1].clear}}',
    STATE + 'let clear=(@values:set<int64>):>bool=>{values.clear return true}\nlet scan=(state:State):>void=>{loop value in state.input and clear(@state.input) {}}',
]


@pytest.mark.parametrize('source', CASES)
def test_hosted_disjoint_iterator_routes(source):
    check.typecheck_and_resolve(SrcFile(None, source))


@pytest.mark.parametrize('source', ERRORS)
def test_hosted_overlapping_iterator_routes(source):
    with pytest.raises(UserError, match='cannot mutate .* while iterating it'):
        check.typecheck_and_resolve(SrcFile(None, source))


def test_native_iterator_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(source_values, 'CASES', CASES)
    monkeypatch.setattr(source_values, 'ERROR_CASES', ERRORS)
    source_values.test_native_source_values(tmp_path, function_types=True)
