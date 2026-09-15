"""Helper reuse follows accessed offsets, independently of map display order."""
from pathlib import Path
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point

ROOT = Path(__file__).resolve().parents[2]
BODY = '''
main=():>int64=>{
    let offsets:dict<string addr>=['keys'->0 'values'->8 'hashes'->16 'indices'->24 'live'->32]
    let original=layouts.Record[40 8 offsets]
    let key=layouts.dictionary_key(original)
    let reordered:dict<string addr>=['live'->32 'indices'->24 'hashes'->16 'values'->8 'keys'->0]
    if layouts.dictionary_key(layouts.Record[40 8 reordered]) not=? key return 1
    loop name in ['keys' 'values' 'hashes' 'indices' 'live'] {
        let changed=offsets
        changed[name]=48
        if layouts.dictionary_key(layouts.Record[56 8 changed]) =? key return 2
    }
    let set_offsets=offsets
    set_offsets.pop('values');
    if layouts.dictionary_key(layouts.Record[40 8 set_offsets]) =? key return 3
    if layouts.dictionary_key(original) not=? key return 4
    return 42
}
'''


def test_dictionary_layout_key(tmp_path):
    source = tmp_path / 'layout-key.dewy'
    source.write_text(f'import p"{ROOT / "dewy/bootstrap/backend/udewy/layouts.dewy"}" as layouts\n' + BODY)
    output = source.with_suffix('.udewy')
    output.write_text(codegen(SrcFile.from_path(source), debug_locations=False))
    for target in ('x86_64', 'c'):
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        run = subprocess.run([cache_artifact(output).resolve()], capture_output=True,
                             text=True, timeout=20, check=False)
        assert run.returncode == 42, (target, run.returncode, run.stdout, run.stderr)
