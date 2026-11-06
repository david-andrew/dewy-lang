"""Keep isolated checker services bound to their existing effect doubles."""


def effect_services(text, modules):
    if "ownership_finalize = " in modules.get("ownership.jo", ""):
        text = text.replace("ownership_hooks.dewy", "ownership.jo").replace(
            "ownership_hooks.jo", "ownership.jo")
    if any(name + " = " in modules.get("secrets.jo", "")
           for name in ("secret_cast", "secret_member", "secret_unary")):
        text = text.replace("secret_checks.dewy", "secrets.jo").replace(
            "secret_checks.jo", "secrets.jo")
    if 'dc_force_all = ' in modules.get('lazy_bodies.jo', ''):
        text = text.replace('lazy_force.dewy', 'lazy_bodies.jo').replace('lazy_force.jo', 'lazy_bodies.jo')
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
