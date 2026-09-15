"""Lowering reuses queries only while their discovery/body inputs are stable."""
from types import SimpleNamespace

from dewy.backend.udewy import codegen, lower
from dewy.reporting import SrcFile
from test_dict_rebuild_helpers import check_generated


def test_runtime_helper_lookup_follows_discovery_and_compilation_lifetime():
    state = SimpleNamespace(functions=[], runtime_helpers={})
    find = lambda name: lower._Lowerer._runtime_helper(state, name)
    assert find('_arena_alloc') is None
    helper = SimpleNamespace(logical_name='library._arena_alloc', symbol='before')
    state.functions.append(helper)
    assert find('_arena_alloc') is helper
    # A later matching declaration cannot displace the original selection.
    state.functions.append(SimpleNamespace(logical_name='later._arena_alloc'))
    helper.symbol = 'allocated_symbol'
    assert find('_arena_alloc').symbol == 'allocated_symbol'
    assert find('_arena_release') is None
    release = SimpleNamespace(logical_name='library._arena_release')
    state.functions.append(release)
    assert find('_arena_release') is release
    bare = SimpleNamespace(functions=[], runtime_helpers={})
    assert lower._Lowerer._runtime_helper(bare, '_arena_alloc') is None


def test_string_ownership_analyses_share_the_transformed_body_index(tmp_path, monkeypatch):
    original = lower._Lowerer._local_initializers
    visits = {}

    def counted(self, literal):
        prior = visits.get(id(literal))
        visits[id(literal)] = (literal, 1 if prior is None else prior[1] + 1)
        return original(self, literal)

    monkeypatch.setattr(lower._Lowerer, '_local_initializers', counted)
    source = SrcFile(None, '''
        let text=(n:int64):>string=>"item {n}"
        let choose=(n:int64):>string=>{
            let result=text(n)
            loop i in 0..2 {if i =? 2 {result=text(n+i)}}
            return result
        }
        let main=():>int64=>{
            let words:array<string>=[]
            words.push(choose(40))
            let saved=words
            words.push(choose(1))
            return if saved.length =? 1 and saved[0] =? 'item 42' and words[1] =? 'item 3' 42 else 0
        }
    ''')
    emitted = codegen(source, debug_locations=False)
    assert visits and all(count == 1 for _, count in visits.values())
    check_generated(emitted, tmp_path / 'ownership-indexes.udewy')


def test_captured_write_inside_keyword_argument_is_rejected():
    import pytest
    from dewy.semantic.errors import NotImplementedYet

    source = SrcFile(None, '''
        let consume=(value:int64):>int64=>value
        let main=():>int64=>{
            let n:int64=0
            let inner=():>int64=>consume(value={n=7\n0})
            inner();
            return n
        }
    ''')
    with pytest.raises(NotImplementedYet, match='writing to `n`'):
        codegen(source, debug_locations=False)


def test_storage_cleanup_shares_unchanged_children_without_merging_occurrences():
    from dewy.backend.udewy.lowering_shared import replace_changed
    from dewy.semantic import hir
    from dewy.reporting import Span

    loc = Span(0, 0)
    leaf = hir.Integer(loc, 'int64', '0d', 42)
    body = hir.Block(loc, 'void', [leaf], True)
    assert replace_changed(body, items=[leaf]) is body
    # An equal, distinct occurrence is a real replacement. The old list and
    # leaf must remain available to its earlier analysis/diagnostic consumers.
    other = hir.Integer(loc, 'int64', '0d', 42)
    updated = replace_changed(body, items=[other])
    assert updated is not body and updated.items[0] is other
    assert body.items[0] is leaf


def test_storage_cleanup_matches_unconditionally_rebuilt_output(monkeypatch):
    from dataclasses import replace
    from dewy.backend.udewy import lowering_strings

    source = SrcFile(None, '''
        main=():>int64=>{
            let output:array<string>=[]
            loop i in 0..2 {
                let data=[text="item {i}" numbers=[i i+1]]
                if i=?1 continue
                output.push(data.text)
            }
            if output.length=?2 and output[1]=?'item 2' return 42
            return 0
        }
    ''')
    shared = codegen(source, debug_locations=False)
    monkeypatch.setattr(lower, 'replace_changed', replace)
    monkeypatch.setattr(lowering_strings, 'replace_changed', replace)
    rebuilt = codegen(source, debug_locations=False)
    assert shared == rebuilt
