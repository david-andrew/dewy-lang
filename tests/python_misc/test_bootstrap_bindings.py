"""Run bootstrap binding, lexical-scope, and HIR storage-route operations."""

import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def test_native_bindings_scopes_and_routes(tmp_path):
    program = '''
from reporting import Span
import p"BINDINGS" as bindings
import p"HIR" as hir
main = ():>int64 => {
    let registry = bindings.Registry[]
    let loc = Span[0 1]
    let first = bindings.allocate(@registry 10 'x' 'value' loc)
    let second = bindings.allocate_param(@registry 'x' 0 loc)
    if first =? second return 1
    if bindings.binding_at(registry first).name not=? 'x' return 2
    if registry.by_syntax.get(10) not=? first return 3
    let scopes:array<bindings.Scope> = []
    let outer = bindings.push_scope(@scopes none)
    bindings.bind(@scopes outer 'x' first)
    let inner = bindings.push_scope(@scopes outer)
    if bindings.lookup(scopes inner 'x') not=? first return 4
    bindings.bind(@scopes inner 'x' second)
    if bindings.lookup(scopes inner 'x') not=? second return 5
    if bindings.lookup(scopes outer 'x') not=? first return 6
    if bindings.lookup(scopes inner 'missing') isnt? none return 7

    let route = bindings.route_id(@registry first ['bag' 'items'] 0 loc)
    if bindings.route_id(@registry first ['bag' 'items'] 0 loc) not=? route return 8
    let sibling = bindings.route_id(@registry first ['other'] 0 loc)
    if sibling =? route return 9
    if bindings.routes_under(registry first ['bag']).length not=? 1 return 10
    if bindings.routes_under(registry second []).length not=? 0 return 11

    let nodes:array<hir.AST> = []
    let root = hir.append_node(@nodes hir.ExpressedIdentifier[loc=loc value_type=0 name='x' binding_id=first])
    let bag = hir.append_node(@nodes hir.MemberAccess[loc=loc value_type=0 value=root name='bag'])
    let items = hir.append_node(@nodes hir.MemberAccess[loc=loc value_type=0 value=bag name='items'])
    let view = hir.append_node(@nodes hir.ValueCast[loc=loc value_type=0 expr=items])
    if bindings.array_route_id(view nodes @registry) not=? route return 12
    let path = bindings.access_path(view nodes)
    if path.root not=? view or path.steps.length not=? 0 return 13
    path = bindings.access_path(view nodes facts=true)
    let names = bindings.member_fields(path nodes)
    if names is? none return 14
    if names.join('.') not=? 'bag.items' return 15
    let index = hir.append_node(@nodes hir.Index[loc=loc value_type=0 array=items index=root constant_index=none])
    if bindings.array_route_id(index nodes @registry) isnt? none return 16
    if bindings.member_fields(bindings.access_path(index nodes) nodes) isnt? none return 17
    return 42
}
'''.replace('BINDINGS', str(ROOT / 'dewy/bootstrap/semantic/bindings.dewy')).replace('HIR', str(ROOT / 'dewy/bootstrap/semantic/hir.dewy'))
    source = tmp_path / 'bindings.dewy'
    source.write_text(program)
    lowered = tmp_path / 'bindings.udewy'
    lowered.write_text(codegen(SrcFile.from_path(source)))
    assert entry_point(lowered, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(lowered).resolve()], check=False, capture_output=True, timeout=30)
    assert result.returncode == 42, result.stderr.decode()
