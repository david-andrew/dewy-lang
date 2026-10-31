"""Canonical plans follow write dependencies without changing proof transfer."""
import subprocess

from tests.support import ROOT, compiler  # noqa: F401


def test_fact_plan_dependencies(compiler, tmp_path):
    source = tmp_path / 'fact_plans.jo'
    source.write_text(''.join(f"use '{ROOT / 'compiler' / name}'\n" for name in
                              ('facts.jo', 'effects.jo', 'places.jo', 'types.jo',
                               'checker_types.dewy', 'refinement_types.dewy', 'check.jo', 'effect_types.dewy',
                               'exact.jo', 'ast.jo', 'floats.jo')) + '''
init_types()
fns.resize(4)
effect_graph_reset()
p = PlaceIdentity(.formal, 2, 1)
effect_add(2, EffectEvent(EffectAtom(.write, p), 81))
effect_summaries[2].done = true
version = fact_plan_version(2)
assert(version != 0)
plan = FactSlice(flags = [1, 3, 7], base = 101, plan = 41, callees = [2], versions = [version])
assert(fact_plan_current(plan))
# Non-write events and witness changes do not change demand edges.
effect_add(2, EffectEvent(EffectAtom(.alloc), 82))
assert(fact_plan_current(plan))
effect_graph_reset(true)
effect_add(2, EffectEvent(EffectAtom(.write, p), 91))
assert(not fact_plan_current(plan))
effect_summaries[2].done = true
assert(fact_plan_current(plan))
# A static finalizer takes precisely the probe's plan.
fact_policy = .RequireStatic
fact_slice_cache[(1 << 4) | 6] = plan
fact_slice_prepare(1)
assert(fact_slice.plan == 41 and fact_slice.flags == [1, 3, 7])
# A probe-only floor demand never becomes the finalizer's canonical plan.
fact_slice_cache.remove(20)
plan.probe_only = true
fact_slice_cache[22] = plan
fact_slice_prepare(1)
assert(fact_slice.plan != 41)
plan.probe_only = false
fact_slice_cache[20] = plan
fact_slice_cache[22] = plan
# An added write, escape, and region-budget widening each invalidate it.
effect_add(2, EffectEvent(EffectAtom(.write, PlaceIdentity(.global, 0, 3)), 92))
assert(not fact_plan_current(plan))
# The established mode's original demand budget stays fixed. A new mode
# cannot adopt this stale plan: it builds its own from the new dependencies.
fact_slice_prepare(1)
assert(fact_slice.plan == 41)
fact_slice_cache.remove(20)
fact_slice_prepare(1)
assert(fact_slice.plan != 41)
plan.versions = [fact_plan_version(2)]
effect_add(2, EffectEvent(EffectAtom(.escape), 93))
assert(not fact_plan_current(plan))
effect_graph_reset()
loop i in [1..33): effect_add(2, EffectEvent(EffectAtom(.write, place_project(p, i)), i))
effect_summaries[2].done = true
plan.versions = [fact_plan_version(2)]
assert(fact_plan_current(plan))
effect_add(2, EffectEvent(EffectAtom(.write, place_project(p, 33)), 33))
assert(not fact_plan_current(plan))
# Independently built, identical slices retain the old reusable-run decision;
# canonical identity avoids this comparison only for a shared plan.
fact_slice_cache[20] = plan
run = FactProbeRun({}, false, 42, [1, 3, 7], 101, [], [])
assert(fact_probe_reusable(1, run))
run.slice = [1, 1, 7]
assert(not fact_probe_reusable(1, run))
# Exact and index decisions are dynamic demand inputs too. A completed
# probe must not silently carry its earlier roots into a fresh finalizer.
store = mk(.int_lit, 0)
exact_reserve(store)
exact_marks[store] = u8(2)
fact_deferred_proving = true
roots = FactSlice(exact_demands = [store])
assert(fact_plan_current(roots))
exact_decide(store, true)
assert(not fact_plan_current(roots))
fact_deferred_proving = false
index = mk(.index, 0)
roots = FactSlice(index_demands = [index])
assert(fact_plan_current(roots))
add_flag(index, NF_INBOUNDS)
assert(not fact_plan_current(roots))
# Integer-to-float roots depend on the current owner while the finalizer
# asks whether a completed probe can be reused, before installing its owner.
ff_conversions[9] = true
fact_owner = 9
assert(not fact_plan_current(FactSlice()))
assert(fact_plan_current(FactSlice(float_context = true)))
fact_owner = 0
ff_conversions = {}
# Body rewrites discard all modes and the completed probe, even when the
# same function ID and dependency rows survive the rewrite.
fact_probe_runs[1] = FactProbeRun({}, false, 41, [], 0, [], [])
fact_plan_forget(1)
assert(not fact_slice_cache.has(20) and not fact_slice_cache.has(22))
assert(not fact_probe_runs.has(1))
print("ok")
''')
    binary = tmp_path / 'fact_plans'
    built = subprocess.run([compiler, 'build', source, '-o', binary],
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([binary], capture_output=True, text=True, timeout=10)
    assert ran.returncode == 0 and ran.stdout == 'ok\n', ran.stdout + ran.stderr
