"""Large finite iterator cardinalities must not wrap into empty ranges."""
import subprocess
import re
from pathlib import Path

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from tests.python_misc.test_bootstrap_lowering import build_native_lowering_driver
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]


def check_wide_ranges(binary, tmp_path):
    source = ROOT / 'tests/fixtures/native_wide_range_counts.dewy'
    result = subprocess.run([binary, source], capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    for label, code in [('native', result.stdout), ('hosted', codegen(SrcFile.from_path(source), debug_locations=False))]:
        output = tmp_path / f'wide-ranges-{label}.udewy'
        output.write_text(code)
        for target in ['x86_64', 'c']:
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                 text=True, timeout=15, check=False)
            assert run.returncode == 42, (label, target, run.returncode, run.stdout, run.stderr)

    # Seed the lowered cursor near its last entry. Reaching these boundaries
    # from -1 would require 2^63/2^64 iterations; this tests the generated
    # machine-word state transition below source-level representation proofs.
    for count in [1 << 63, 1 << 64]:
        boundary = tmp_path / 'wide-boundary.dewy'
        boundary.write_text(f'main=():>int64=>{{let n:int64=0 loop i in 0..{count-1} and n <? 4 {{n+=1}} return n}}')
        result = subprocess.run([binary, boundary], capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        code, changes = re.subn(r'(let \w+:int64 = )-1\b',
                                lambda match: match[1] + str(count - 3), result.stdout)
        assert changes == 1, 'expected exactly one cursor initializer in this scalar kernel'
        output = tmp_path / f'wide-boundary-{count}.udewy'
        output.write_text(code)
        for target in ['x86_64', 'c']:
            assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
            run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                 text=True, timeout=15)
            assert run.returncode == 2, (count, target, run.returncode, run.stdout, run.stderr)


def test_native_wide_ranges(tmp_path):
    check_wide_ranges(build_native_lowering_driver(tmp_path), tmp_path)
