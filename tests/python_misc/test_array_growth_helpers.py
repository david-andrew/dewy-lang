"""Array relocation shares code by stored width and preserves owned values."""
import re

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from test_dict_rebuild_helpers import ROOT, check_generated


def test_array_growth_values(tmp_path):
    source = ROOT / 'tests/fixtures/native_array_growth_helpers.dewy'
    code = codegen(SrcFile.from_path(source), debug_locations=False)
    check_generated(code, tmp_path / 'growth.udewy')


def test_array_growth_code_is_shared():
    def generate(count):
        functions = '\n'.join(
            f'grow{i}=(@xs:array<int64>):>void=>{{xs.reserve({100+i})}}'
            for i in range(count))
        calls = '\n'.join(f'grow{i}(@xs)' for i in range(count))
        return codegen(SrcFile(None, functions +
            f'\nmain=():>int64=>{{let xs:array<int64>=[42]\n{calls}\n$runtime_assert xs.length >? 0\nreturn xs[0]}}'),
            debug_locations=False)

    small, large = generate(1), generate(12)
    definition = r'^let (__dewy_grow_array_\w*) = '
    assert len(re.findall(definition, small, re.M)) == len(re.findall(definition, large, re.M)) > 0
    assert 0 < len(large) - len(small) < 25_000
