"""Cold dictionary rebuild code is shared without changing its ownership."""
import re
import subprocess
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_generated(code, output):
    output.write_text(code)
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=20, check=False)
        assert result.returncode == 42, (target, result.returncode, result.stdout, result.stderr)


def test_hosted_dictionary_rebuild_helpers(tmp_path):
    source = ROOT / 'tests/fixtures/native_dict_rebuild_helpers.dewy'
    code = codegen(SrcFile.from_path(source), debug_locations=False)
    assert '__dewy_rebuild_dict_' in code
    check_generated(code, tmp_path / 'rebuild.udewy')


def test_repeated_lookup_sites_share_rebuild_code():
    def generate(count):
        funcs = '\n'.join(f'read{i}=(d:dict<int64 int64>):>int64=>d.get({i} default=0)'
                          for i in range(count))
        calls = '+'.join(f'read{i}(d)' for i in range(count))
        text = funcs + f'\nmain=():>int64=>{{let d:dict<int64 int64>=[0->42] return {calls}}}'
        return codegen(SrcFile(None, text), debug_locations=False)

    small, large = generate(1), generate(12)
    # Prelude helpers occur in both. Adding lookup sites must not add rebuild
    # implementations, and the calls must actually survive reachable lowering.
    definition = r'^let (__dewy_rebuild_dict_\w*) = '
    assert len(re.findall(definition, large, re.M)) == len(re.findall(definition, small, re.M)) > 0
    assert len(large) > len(small)
    assert len(large) - len(small) < 90_000
