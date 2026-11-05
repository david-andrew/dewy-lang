"""Keep isolated checker services bound to their existing effect doubles."""


def contract_services(text, modules):
    # Whole-compiler differentials supply the real state and switch one leaf.
    # Isolated checker drivers instead own only the effect callbacks they use.
    if 'struct EffectSummary:' in modules.get('effects.jo', ''):
        return text
    return text.replace('effect_contracts.dewy', 'effects.jo').replace(
        'effect_contracts.jo', 'effects.jo')
