"""Arrays own their element strings: stores copy, releases free elements, and copies of string arrays get their own strings."""
from tests.python_misc.test_scalar_projection import execute

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _compile(source: str) -> str:
    return codegen(SrcFile(None, source))


def _function(emitted: str, name: str) -> str:
    start = emitted.index(f'let {name} = ')
    end = emitted.find('\nlet ', start)
    return emitted[start:] if end == -1 else emitted[start:end]


BUILD = (
    'let build = (n:int64):>int64 => {\n'
    '    let parts:array<string> = []\n'
    '    loop i in [0..4) { parts.push"{i}-{n}" }\n'
    '    return parts.length\n'
    '}\n'
    'let main = ():>int64 => build(3)\n'
)


def test_growing_string_array_releases_every_owned_element(tmp_path):
    source = BUILD.split('let main =')[0].replace('[0..4)', '[0..64)') + '''
main=():>int64=>{
    if build(3) not=? 64 return 1
    let before:int64=_arena_live_bytes
    loop i in 0.. and i <? 100 {if build(3) not=? 64 return 2}
    if _arena_live_bytes not=? before return 3
    return 42
}
'''
    execute(tmp_path, 'owned-string-growth', _compile(source))


def test_element_reads_copy_when_stored_or_returned() -> None:
    emitted = _compile(
        'let head = (xs:array<string>):>string => {\n'
        '    if xs.length >? 0 { return xs[0] }\n'
        '    return ""\n'
        '}\n'
        'let main = ():>int64 => {\n'
        '    let xs = ["longer" "words"]\n'
        '    let kept:array<string> = []\n'
        '    loop x in xs { kept.push(x) }\n'
        '    return kept.length + head(kept).length\n'
        '}\n'
    )
    head = _function(emitted, 'head')
    assert 'escaping' in head   # `return xs[0]`: the caller gets its own copy


def test_a_copy_of_a_string_array_owns_its_own_elements() -> None:
    emitted = _compile(
        'let main = ():>int64 => {\n'
        '    let xs:array<string> = []\n'
        '    xs.push"only"\n'
        '    let copy:array<string> = xs\n'
        '    xs = []\n'
        '    return copy.length\n'
        '}\n'
    )
    assert '__dewy_string_clone(' in emitted     # the copy clones owned elements …
    assert 'let __dewy_string_clone = ' in emitted   # … through the one synthesized helper


    # The shared-array detachment helper may need a clone fallback, even
    # when this particular loop never shares its buffer.


def test_stored_views_of_static_text_survive_loop_region_reuse(tmp_path) -> None:
    import subprocess

    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    output = tmp_path / 'static_views.udewy'
    output.write_text(_compile('''
const alphabet='0123456789'
let main = ():>int64 => {
    let parts:array<string>=[]
    loop i in [0..4) { parts.push(alphabet[i]) }
    printl(parts.join)
    let slices:array<string>=[]
    loop i in [0..4) { slices.push(alphabet[i..i+2]) }
    printl(slices.join)
    return 0
}
'''))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == '0123\n012123234345\n'


def test_cloned_unicode_views_keep_relative_grapheme_boundaries(tmp_path) -> None:
    import subprocess

    from udewy.cache import cache_artifact
    from udewy.frontend import EntryPointOptions, entry_point

    source = r'''
let inspect = (items:array<string>):>int64 => {
    let copy=items
    items.clear
    $runtime_assert copy.length =? 3
    let view=copy[0]
    $runtime_assert view.length =? 5
    $runtime_assert view[0] =? "e\u0301"
    $runtime_assert view[1] =? "👩‍👩‍👧‍👦"
    $runtime_assert view[2] =? "🇺🇸"
    $runtime_assert view[3] =? "\r\n"
    $runtime_assert view[4] =? "z"
    $runtime_assert copy[1].length =? 0
    let last=copy[2]
    $runtime_assert last.length =? 1
    $runtime_assert last[0] =? "🙂"
    return 0
}
let main = ():>int64 => {
    let text:string="!e\u0301👩‍👩‍👧‍👦🇺🇸\r\nz?"
    let items:array<string>=[]
    items.push(text[1..6))
    items.push("")
    items.push("🙂")
    loop i in 0..20 {inspect(items);}
    return inspect(items)
}
'''
    emitted = _compile(source)
    clone = _function(emitted, '__dewy_string_clone')
    assert 'boundary_index' in clone
    assert 'grapheme_break' not in clone
    output = tmp_path / 'cloned_unicode_views.udewy'
    output.write_text(emitted)
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_string_copy_survives_owner_rebinding(tmp_path):
    """A callee-owned descriptor must not dangle in another local or view."""
    source = '''
let identity=(s:string):>string=>s
let saved=():>string=>{
    let source=identity('ab'+'cd')
    let old=source
    let again=old
    source='x'
    old='y'
    return again
}
let main=():>int64=>{
    let source=identity('abcd')
    if source.length <? 3 return 1
    let slice=source[1..3)
    source='z'
    return if saved()=?'abcd' and slice=?'bc' and source=?'z' 42 else 0
}
'''
    execute(tmp_path, 'local-string-owners', _compile(source))
