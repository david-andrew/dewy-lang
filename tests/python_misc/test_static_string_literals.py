"""Literal descriptors are static data, including grapheme offset relocations."""
import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_large_and_unicode_literals_survive_repeated_calls(tmp_path):
    source = '''
choose=(index:int64):>string=>{
    if index =? 0 return "LONG_ASCII"
    if index =? 1 return "é👩‍👩‍👧‍👦🇺🇸"
    return ""
}
exercise=():>int64=>{
    loop i in 0.. and i <? 32 {
        let text=choose(0)
        if text.length not=? 4096 return 1
        if text[4095] not=? "A" return 2
        let clusters=choose(1)
        if clusters.length not=? 3 return 3
        if clusters[1] not=? "👩‍👩‍👧‍👦" return 4
        if clusters[2] not=? "🇺🇸" return 5
        if choose(2).length not=? 0 return 6
    }
    return 42
}
main=():>int64=>{
    if exercise() not=? 42 return 8
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 8 {if exercise() not=? 42 return 9}
    if _arena_live_bytes not=? before return 7
    return 42
}
'''.replace('LONG_ASCII', 'A' * 4096)
    code = codegen(SrcFile(None, source), debug_locations=False)
    # Runtime helpers and literal data count too. Filling 4,097 boundary
    # entries with individual runtime stores used to exceed this budget.
    assert len(code.encode()) < 160_000
    output = tmp_path / 'static-literals.udewy'
    output.write_text(code)
    for target in ['x86_64', 'c']:
        assert entry_point(output, [], EntryPointOptions(compile_only=True, target=target)) == 0
        result = subprocess.run([cache_artifact(output)], capture_output=True,
                                text=True, timeout=15, check=False)
        assert result.returncode == 42, result.stdout + result.stderr
