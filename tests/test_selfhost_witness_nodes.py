"""wit_text and wit_slice_at in witness_nodes preserve frozen Jo diagnostic bytes."""
import pytest

from tests import selfhost_lsp_double
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_driver_cli import run

pytestmark = pytest.mark.nightly


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_witness_nodes_match_twin(compiler, tmp_path, monkeypatch, release):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    driver = '''use 'main.jo'
use 'witness_nodes.dewy'
main = ():
    if args().len() > 1 and args()[1] == "wit-empty":
        print("EMPTY {wit_text(0)}|{wit_text(-1)}|{wit_text(1, 9)}|{wit_text(1, 10000000007)}")
    else:
        lower_test_cli()
'''
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', driver)
    original = selfhost_lsp_double.cached_driver
    monkeypatch.setattr(selfhost_lsp_double, 'cached_driver',
                        lambda compiler, path, _, modules: original(compiler, path, release, modules))
    binaries = selfhost_lsp_double.leaf_compilers(compiler, tmp_path, ('witness_nodes',))
    assert [run(b, ['wit-empty'], tmp_path) for b in binaries] == [(0, 'EMPTY |||\n', '')] * 2
    # Real checked arenas exercise captures/aliases, fields, projected and library
    # places, arithmetic, spread blocks, depth limits, and all slice obligations.
    cases = sorted(p for group in ('witness', 'witness_bounds', 'slice')
                   for p in (ROOT / 'tests/cases' / group).glob('*.dewy'))
    assert len(cases) > 60
    shown = []
    for policy in ((), ('--internal-fact-policy=require-static',),
                   ('--internal-fact-policy=require-static-all',)):
        for source in cases:
            args = [*policy, 'check', str(source)]
            actual, expected = [run(b, args, tmp_path) for b in binaries]
            assert actual == expected, (release, args, actual, expected)
            shown.append(actual[2])
    # The obligations CLI traverses the diagnostic collection exit as well.
    for name in ('slice_every_missing', 'contract_help', 'floor_relation'):
        args = ['check', '--obligations', str(ROOT / f'tests/cases/witness/{name}.dewy')]
        actual, expected = [run(b, args, tmp_path) for b in binaries]
        assert actual == expected, (release, args, actual, expected)
    text = '\n'.join(shown)
    for phrase in ('cannot prove', 'help:', 'lower bound', 'upper bound', 'ordered bounds'):
        assert phrase in text, phrase
