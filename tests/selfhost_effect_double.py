"""Keep isolated checker services bound to their existing effect doubles."""


def effect_services(text, modules):
    if 'concurrency_tasks:' not in modules.get('concurrency.jo', ''):
        text = text.replace('concurrency_types.dewy', 'concurrency.jo').replace(
            'concurrency_types.jo', 'concurrency.jo')
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
