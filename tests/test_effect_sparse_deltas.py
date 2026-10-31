"""Summary deltas retain witnesses across appends, self edges and widening."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def test_effect_delta_generations(compiler, tmp_path):
    source = tmp_path / 'effect_deltas.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / name}'\n" for name in
                              ('effects.jo', 'places.jo', 'types.jo', 'ast.jo',
                               'checker_types.dewy', 'check.jo', 'dewy_reader_types.dewy', 'effect_types.dewy')) + '''
init_types()
fns.resize(4)
effect_limit = fns.len()
effect_summaries = fill(EffectSummary(), effect_limit)
# Two distinct dependencies, plus a duplicate call: retain the first witness.
effect_summaries[1].edges = [EffectEdge(2, 71, []), EffectEdge(3, 72, []), EffectEdge(2, 73, [])]
effect_add(2, EffectEvent(EffectAtom(.alloc), 81))
assert(effect_propagate(1))
assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 81, 71, 2)])
effect_add(3, EffectEvent(EffectAtom(.io), 82))
assert(effect_propagate(1))
effect_add(2, EffectEvent(EffectAtom(.block), 83))
assert(effect_propagate(1))
assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 81, 71, 2), EffectEvent(EffectAtom(.io), 82, 72, 3), EffectEvent(EffectAtom(.block), 83, 71, 2)])
assert(not effect_propagate(1))
# A self-edge substitutes the two formal places. Its snapshot sees only the
# old prefix, then the next pass consumes the newly appended event.
effect_graph_reset()
a = PlaceIdentity(.formal, 1, 1)
b = PlaceIdentity(.formal, 1, 2)
effect_summaries[1].edges = [EffectEdge(1, 74, [b, a])]
effect_add(1, EffectEvent(EffectAtom(.write, a), 84))
assert(effect_propagate(1))
assert(not effect_propagate(1))
assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.write, a), 84), EffectEvent(EffectAtom(.write, b), 84, 74, 1)])
# Widening replaces a full row by its root. The shorter new generation must
# be replayed, including the first witness, despite the old consumed prefix.
effect_graph_reset()
formal = PlaceIdentity(.formal, 2, 1)
actual = PlaceIdentity(.global, 0, 1)
effect_summaries[1].edges = [EffectEdge(2, 75, [actual])]
loop i in [1..33): effect_add(2, EffectEvent(EffectAtom(.write, place_project(formal, i)), 100 + i))
assert(effect_propagate(1))
assert(effect_summaries[1].events.len() == 32)
effect_add(2, EffectEvent(EffectAtom(.write, place_project(formal, 33)), 133))
assert(effect_summaries[2].events.len() == 1)
assert(effect_propagate(1))
assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.write, actual), 101, 75, 2)])
assert(not effect_propagate(1))
# Graph reset discards consumed prefixes even when body inventories survive.
effect_graph_reset(true)
effect_summaries[1].edges = [EffectEdge(2, 76, [])]
effect_add(2, EffectEvent(EffectAtom(.alloc), 85))
assert(effect_propagate(1))
assert(effect_summaries[1].events == [EffectEvent(EffectAtom(.alloc), 85, 76, 2)])
print("ok")
''')
    binary = tmp_path / 'effect_deltas'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == 'ok\n', ran.stdout + ran.stderr


def test_effect_unused_import_is_still_checked(compiler, tmp_path):
    module = tmp_path / 'unasked.dewy'
    module.write_text('bad=():>void & no_effects=>printl"must be rejected"\n')
    source = tmp_path / 'main.dewy'
    source.write_text('from p"unasked.dewy" import bad\nmain=()=>printl"unused"\n')
    built = subprocess.run([compiler, 'build', source, '-o', tmp_path / 'unused'],
                           capture_output=True, text=True, timeout=30)
    assert built.returncode != 0, built.stdout + built.stderr
    assert 'effect contract violation' in built.stderr, built.stderr
    assert 'unasked.dewy' in built.stderr, built.stderr
