"""Keep isolated checker services bound to their existing effect doubles."""
from tests.selfhost_homes_checks import CHECKS_HOMES, LEAF_HOMES as CHECKS_LEAVES, checker_homes
from tests.selfhost_homes_editor import LEAF_HOMES as EDITOR_LEAVES
from tests.selfhost_homes_facts import LEAF_HOMES as FACTS_LEAVES, facts_homes
from tests.selfhost_homes_process import LEAF_HOMES as PROCESS_LEAVES
from tests.selfhost_homes_reader import LEAF_HOMES as READER_LEAVES
from tests.selfhost_homes_targets import LEAF_HOMES as TARGETS_LEAVES

# (a leaf moved out of a Jo module without state of its own, by family: see tests/selfhost_homes_*.py)
LEAF_HOMES = {**CHECKS_LEAVES, **FACTS_LEAVES, **READER_LEAVES, **TARGETS_LEAVES, **EDITOR_LEAVES, **PROCESS_LEAVES}


def effect_services(text, modules):
    text = checker_homes(text, modules)
    text = facts_homes(text, modules)
    for leaf, home in LEAF_HOMES.items():
        if home in modules and leaf + '.dewy' not in modules and leaf + '.jo' not in modules:
            text = text.replace(leaf + '.dewy', home).replace(leaf + '.jo', home)
    if 'struct ParSafeVia:' not in modules.get('concurrency.jo', ''):
        for stem in ('concurrency_types', 'concurrency_tasks'):
            text = text.replace(stem + '.dewy', 'concurrency.jo').replace(
                stem + '.jo', 'concurrency.jo')
    if 'struct IsolationRow:' not in modules.get('isolation.jo', ''):
        text = text.replace('isolation_ops.dewy', 'isolation.jo').replace(
            'isolation_ops.jo', 'isolation.jo')
    # Whole-compiler differentials supply the real state and switch one leaf.
    # Isolated checker drivers instead own only the effect callbacks they use.
    if 'struct EffectSummary:' in modules.get('effects.jo', ''):
        return text
    for stem in ('effect_contracts', 'effect_control', 'effect_sources'):
        text = text.replace(stem + '.dewy', 'effects.jo').replace(
            stem + '.jo', 'effects.jo')
    return text


def type_helpers_home(text):
    """An isolated harness whose types.jo is a double reads the moved type helpers from that double."""
    for stem in ('type_ops', 'word_overflow'):
        text = text.replace(stem + '.dewy', 'types.jo').replace(stem + '.jo', 'types.jo')
    return text
