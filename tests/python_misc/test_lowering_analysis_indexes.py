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
