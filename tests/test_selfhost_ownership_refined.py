"""ownership_types preserves owner properties through refinement wrappers."""
import pytest
from tests.support import compiler
from tests import test_selfhost_ownership_types as original

PROBE = '''
    ref_res = kind(.refined, res)
    ref_arr = kind(.refined, arr_res)
    opt_ref = kind(.opt, ref_arr)
    nested = kind(.refined, ref_arr)
    print("refined", ownership_nominal(ref_res), ownership_type(ref_arr), ownership_contains(opt_ref), ownership_copyable(ref_arr), ownership_decl_copyable(ref_arr), ownership_layout(ref_arr), ownership_inline(ref_res), ownership_type(nested))
'''


def compare_refined(compiler, tmp_path, release, monkeypatch):
    driver = original.DRIVER.replace('    print("ok")', PROBE + '    print("ok")')
    monkeypatch.setattr(original, 'DRIVER', driver)
    original.test_ownership_types_twins(compiler, tmp_path, release)
    for extension in ('dewy', 'jo'):
        import subprocess
        ran = subprocess.run([tmp_path / extension / 'driver'], capture_output=True, timeout=30)
        assert b'refined true true true false false true true true\n' in ran.stdout, ran.stdout[-800:]


@pytest.mark.core_quick
@pytest.mark.parametrize('release', [False, True])
def test_refined_ownership_twins(compiler, tmp_path, release, monkeypatch):
    compare_refined(compiler, tmp_path, release, monkeypatch)
