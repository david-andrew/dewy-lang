"""Bounded record-batch reset plans and their whole-array census agree with frozen Jo: the same
messages, IR and bytes for flat and nested records, near misses and default/release builds."""
from tests.selfhost_build_double import compare_builds
from tests.support import compiler  # noqa: F401

BATCH = '''$runtime_checks

{definitions}
step=(@ps:array<P>):>void=>{{
 loop i in 0.. and i <? ps.length {{
{guard}  let x=ps[i].{x}+ps[i].{dx}
  let y=ps[i].{y}{op}ps[i].{dy}
  if x <? {low} or x >=? 100 {{ps[i].{dx}=0-ps[i].{dx}; x=ps[i].{x}}}
  if y <? 0 or y >=? 100 {{ps[i].{dy}=-ps[i].{dy}; y=ps[i].{y}}}
  ps[i].{x}=x
  ps[i].{y}=y
 }}
}}
run=(@ps:array<P> rounds:int64):>void=>{{
 let r:int64=0
 loop r <? rounds {{step(@ps); r+=1}}
}}
main=(args:array<string>)=>{{
 let n=int64(to_int(args[1]) ?? 0)
 let ps:array<P>=[loop i in [0..n) {make}]
 run(@ps 7)
 loop p in ps {{printl(p.{x} p.{y} p.{dx} p.{dy})}}
}}
'''


def programs(tmp_path):
    paths = []
    for nested in (False, True):
        for op, low, guard in (('+', '0', ''), ('-', '0', ''), ('*', '0', ''), ('+', '(-2000000000)', ''), ('/', '0', ''),
                               ('+', '0', '  if i >? 1000000 {break}\n')):
            definitions = 'P:type=[x:int64 y:int64 dx:int64 dy:int64]'
            names = dict(x='x', y='y', dx='dx', dy='dy', make='P[i i+1 1 2]')
            if nested:
                definitions = 'V:type=[x:int64 y:int64]\nP:type=[p:V v:V]'
                names = dict(x='p.x', y='p.y', dx='v.x', dy='v.y', make='P[p=V[i i+1] v=V[1 2]]')
            path = tmp_path / f'batch_{len(paths)}.dewy'
            path.write_text(BATCH.format(definitions=definitions, op=op, low=low, guard=guard, **names))
            paths.append(path.name)
    return paths


def test_exact_reset_walks_matches_twin(compiler, tmp_path, monkeypatch):  # noqa: F811
    results = compare_builds(compiler, tmp_path, monkeypatch, ('exact_reset_walks',), programs(tmp_path),
                             flags=((), ('--release',), ('--ir',)))
    assert sum('fn __h_reset_words_' in r[3] for r in results) == 6
    assert sum(r[2] == 0 for r in results) >= 20
