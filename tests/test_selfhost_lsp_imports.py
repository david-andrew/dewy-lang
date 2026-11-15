"""Custom differential probes follow the same leaf selection as their services."""
import pytest

from tests import selfhost_lsp_double


@pytest.mark.parametrize('quote', ["'", '"'])
def test_custom_probe_imports_follow_twin(tmp_path, monkeypatch, quote):
    leaf = 'lexer_helpers'
    probe = f'use {quote}{leaf}.dewy{quote}\nmain = (): init_keywords()\n'
    service = f'from p"{leaf}.dewy" import init_keywords\n'
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', probe)
    monkeypatch.setattr(selfhost_lsp_double, 'modules_for',
                        lambda *args: {'lexer_scan.dewy': service, f'{leaf}.jo': 'frozen'})
    graphs = []
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, release, modules: graphs.append(modules) or path)

    selfhost_lsp_double.leaf_compilers(None, tmp_path, (leaf,))

    assert graphs[0]['driver.jo'] == probe
    assert graphs[0]['lexer_scan.dewy'] == service
    assert graphs[1]['driver.jo'] == probe.replace('.dewy', '.jo')
    assert graphs[1]['lexer_scan.dewy'] == service.replace('.dewy', '.jo')
    assert graphs[1][f'{leaf}.jo'] == 'frozen'
