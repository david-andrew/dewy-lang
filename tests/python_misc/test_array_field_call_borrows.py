"""Read-only calls on array fields stay bounded and preserve value isolation."""
import subprocess
import sys

import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def _build(tmp_path, source):
    output = tmp_path / 'field_borrow.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    return cache_artifact(output).resolve()


@pytest.mark.skipif(sys.platform != 'linux', reason='native Linux process memory limit')
@pytest.mark.parametrize('argument', ['bag.items', 'boxes[0].items', 'items=bag.items'])
def test_repeated_read_only_field_calls_use_bounded_memory(tmp_path, argument):
    source = '''Entry:type=[value:int64]
Bag:type=[items:array<Entry>]
let read=(items:array<Entry>):>int64=>{
    $runtime_assert items.length >? 0
    return items[0].value
}
let main=():>int64=>{
    let bag=Bag[[]]
    loop i in 0..511 {bag.items.push(Entry[7])}
    let boxes=[bag]
    let total:int64=0
    loop i in 0..99999 {total += read(ARGUMENT)}
    printl(total)
    return 0
}
'''.replace('ARGUMENT', argument)
    binary = _build(tmp_path, source)

    def limit_memory():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))

    result = subprocess.run([binary], capture_output=True, timeout=10, check=False, preexec_fn=limit_memory)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'700000\n'


def test_a_place_alias_still_isolates_the_array_value_argument(tmp_path):
    binary = _build(tmp_path, '''Entry:type=[value:int64]
Bag:type=[items:array<Entry>]
let observe=(before:array<Entry> @bag:Bag):>int64=>{
    $runtime_assert before.length >? 0 and bag.items.length >? 0
    bag.items[0].value=9
    return before[0].value
}
let main=():>int64=>{
    let bag=Bag[[Entry[7]]]
    printl(observe(bag.items @bag))
    $runtime_assert bag.items.length >? 0
    printl(bag.items[0].value)
    return 0
}
''')
    result = subprocess.run([binary], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'7\n9\n'


def test_a_later_argument_cannot_change_an_earlier_array_value(tmp_path):
    binary = _build(tmp_path, '''Entry:type=[value:int64]
Bag:type=[items:array<Entry>]
let change=(@bag:Bag):>int64=>{
    $runtime_assert bag.items.length >? 0
    bag.items[0].value=9
    return 0
}
let observe=(before:array<Entry> unused:int64):>int64=>{
    $runtime_assert before.length >? 0
    return before[0].value
}
let main=():>int64=>{
    let bag=Bag[[Entry[7]]]
    printl(observe(bag.items change(@bag)))
    $runtime_assert bag.items.length >? 0
    printl(bag.items[0].value)
    return 0
}
''')
    result = subprocess.run([binary], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'7\n9\n'


@pytest.mark.skipif(sys.platform != 'linux', reason='native Linux process memory limit')
@pytest.mark.parametrize('object_argument', [False, True])
def test_disjoint_field_places_do_not_force_value_copies(tmp_path, object_argument):
    parameter = 'before:Content' if object_argument else 'before:array<Entry>'
    items = 'before.items' if object_argument else 'before'
    argument = 'bag.content' if object_argument else 'bag.content.items'
    source = '''Entry:type=[value:int64]
Content:type=[items:array<Entry>]
Bag:type=[content:Content calls:int64=0]
let read=(PARAMETER @calls:int64):>int64=>{
    calls += 1
    $runtime_assert ITEMS.length >? 0
    return ITEMS[0].value
}
let main=():>int64=>{
    let bag=Bag[Content[[]]]
    loop i in 0..511 {bag.content.items.push(Entry[7])}
    let total:int64=0
    loop i in 0..99999 {total += read(ARGUMENT @bag.calls)}
    printl(total)
    printl(bag.calls)
    return 0
}
'''.replace('PARAMETER', parameter).replace('ITEMS', items).replace('ARGUMENT', argument)
    binary = _build(tmp_path, source)

    def limit_memory():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))

    result = subprocess.run([binary], capture_output=True, timeout=10, check=False, preexec_fn=limit_memory)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'700000\n100000\n'


def test_a_place_inside_the_same_array_field_keeps_the_before_value(tmp_path):
    binary = _build(tmp_path, '''Entry:type=[value:int64]
Bag:type=[items:array<Entry>]
let observe=(before:array<Entry> @entry:Entry):>int64=>{
    $runtime_assert before.length >? 0
    entry.value=9
    return before[0].value
}
let main=():>int64=>{
    let bag=Bag[[Entry[7]]]
    $runtime_assert bag.items.length >? 0
    printl(observe(bag.items @bag.items[0]))
    $runtime_assert bag.items.length >? 0
    printl(bag.items[0].value)
    return 0
}
''')
    result = subprocess.run([binary], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == b'7\n9\n'
