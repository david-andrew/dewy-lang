"""Keep isolated checker services bound to their existing effect doubles."""


def effect_services(text, modules):
    # Whole-compiler differentials supply the real state and switch one leaf.
    # Isolated checker drivers instead own only the effect callbacks they use.
    if 'struct EffectSummary:' in modules.get('effects.jo', ''):
        return text
    for stem in ('effect_contracts', 'effect_control'):
        text = text.replace(stem + '.dewy', 'effects.jo').replace(
            stem + '.jo', 'effects.jo')
    return text
