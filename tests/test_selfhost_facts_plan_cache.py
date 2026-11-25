"""Plan versions depend on ordered write, opaque and escape atoms, and forgetting evicts every mode."""
import subprocess

from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
import pytest

pytestmark = pytest.mark.nightly


DRIVER = r"""use 'main.jo'
use 'facts_plan_cache.dewy'
use 'facts.jo'
use 'effects.jo'
use 'effect_types.dewy'
main = ():
    effect_summaries.resize(3)
    assert(fact_plan_version(2) == 0)
    effect_summaries[2].done = true
    v = fact_plan_version(2)
    assert(v > 0 and v == fact_plan_version(2))
    effect_summaries[2].stamp += 1
    effect_summaries[2].events.push(EffectEvent(EffectAtom(.alloc), 3))
    assert(fact_plan_version(2) == v)
    kinds: EffectKind[] = [.write, .opaque, .escape]
    loop kind in kinds:
        effect_summaries[2].changed_at += 1
        effect_summaries[2].events.push(EffectEvent(EffectAtom(kind), 4))
        after = fact_plan_version(2)
        assert(after > v)
        v = after
    effect_summaries[2].stamp += 1
    swap = effect_summaries[2].events[2]
    effect_summaries[2].events[2] = effect_summaries[2].events[3]
    effect_summaries[2].events[3] = swap
    assert(fact_plan_version(2) > v)
    loop key in [16..48): fact_slice_cache[key] = FactSlice()
    fact_probe_runs[2] = FactProbeRun({}, false, 0, [], 0, [], [])
    fact_plan_forget(2)
    assert(not fact_probe_runs.has(2))
    loop key in [16..48): assert(fact_slice_cache.has(key) == (key < 32))
    print("ok")
"""


def test_facts_plan_cache_twins(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    for binary in leaf_compilers(compiler, tmp_path, ('facts_plan_cache',)):
        run = subprocess.run([binary], capture_output=True, timeout=60)
        assert (run.returncode, run.stdout) == (0, b'ok\n'), run.stderr
