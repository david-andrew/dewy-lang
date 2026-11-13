"""Session templates observe source edits and never expose a mutable cached graph."""
import os

from tests.compiler_modules import compiler_modules
from tests.module_redirects import module_rewriter
from tests.selfhost_effect_double import effect_services


def test_module_templates_follow_source_content(tmp_path):
    (tmp_path / 'main.jo').write_text('main = ():\n    pass\n')
    leaf = tmp_path / 'leaf.dewy'
    leaf.write_text('value=1\n')
    (tmp_path / 'leaf.jo').write_text('value = 1\n')
    first = compiler_modules(('leaf',), tmp_path)
    first['leaf.dewy'] = 'changed by caller'
    assert compiler_modules(('leaf',), tmp_path)['leaf.dewy'] == 'value=1\n'
    stamp = leaf.stat()
    leaf.write_text('value=2\n')
    os.utime(leaf, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert compiler_modules(('leaf',), tmp_path)['leaf.dewy'] == 'value=2\n'
    extra = tmp_path / 'extra.dewy'
    extra.write_text('value=3\n')
    assert 'extra.dewy' in compiler_modules(('leaf',), tmp_path)
    extra.unlink()
    assert 'extra.dewy' not in compiler_modules(('leaf',), tmp_path)


def test_redirect_plans_preserve_order_and_graph_policy():
    # Trigger several independent home tables and a cascade through a service home.
    graphs = [{}, {'main.jo': ''}, {
        'check.jo': 'secret_cast = x\n',
        'secrets.jo': 'secret_cast = x\n',
        'concurrency.jo': '',
        'effects.jo': 'struct EffectSummary:\n',
        'facts.jo': '\nfact_replace = x\n',
    }]
    text = 'ownership_hooks.dewy secret_checks.dewy facts_routes.dewy concurrency_tasks.dewy effect_control.dewy'
    for modules in graphs:
        rewrite = module_rewriter(effect_services, modules)
        assert rewrite(text) == effect_services(text, modules)

    def cascade(text, modules):
        return text.replace('leaf.dewy', 'leaf.jo').replace('leaf.jo', modules['home'])

    assert module_rewriter(cascade, {'home': 'service.jo'})('leaf.dewy leaf.jo') == 'service.jo service.jo'
