"""Record-family outlining preserves owned fields and prepared result storage."""
from pathlib import Path
import subprocess

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]

PREPARED = '''
Pair:type=[values:array<int64 length=2>]
Root=type of [code:int64]
Leaf=type of Root & [pair:Pair]
Envelope:type=[item:Root known:Pair]
copy_envelope=(value:Envelope):>Envelope=>value
FixedRoot=type of [pair:Pair]
FixedLeaf=type of FixedRoot & [extra:Pair]
copy_fixed=(value:FixedRoot):>FixedRoot=>value
main=():>int64=>{
    let original=Envelope[Leaf[42 Pair[[20 22]]] Pair[[5 6]]]
    let copied=copy_envelope(original)
    copied.known.values[0]=99
    if copied.item isnt? Leaf return 1
    copied.item.pair.values[0]=77
    if original.item isnt? Leaf return 2
    if original.known.values[0] not=? 5 return 3
    if original.item.pair.values[0] not=? 20 return 4
    let fixed:FixedRoot=FixedLeaf[Pair[[20 22]] Pair[[7 8]]]
    let other=copy_fixed(fixed)
    if other isnt? FixedLeaf return 5
    other.extra.values[0]=99
    other.pair.values[0]=77
    if fixed isnt? FixedLeaf return 6
    if fixed.extra.values[0] not=? 7 return 7
    return fixed.pair.values[0]+fixed.pair.values[1]
}
'''


@pytest.mark.parametrize('family', [True, False], ids=['family-growth', 'prepared-storage'])
def test_shared_record_helpers(tmp_path, family):
    source = (SrcFile.from_path(ROOT / 'tests/fixtures/native_record_family_helpers.dewy')
              if family else SrcFile(None, PREPARED))
    code = codegen(source, debug_locations=False)
    if family:
        # The same guarded fixture formerly emitted 2.54 MB. This includes
        # all reachable runtime code, not only the generated copy helpers.
        assert len(code.encode()) < 700_000
    output = tmp_path / 'record-helpers.udewy'
    output.write_text(code)
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == 42, result.stdout + result.stderr
