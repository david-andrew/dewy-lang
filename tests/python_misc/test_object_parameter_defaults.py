"""Aggregate defaults use lazy selection and ordinary value ownership."""

import subprocess

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from udewy.cache import cache_artifact
from udewy.frontend import EntryPointOptions, entry_point


def test_object_defaults_are_lazy_fresh_and_independent(tmp_path):
    source = '''
Box:type = [items:array<int64> label:string]
let make = ():>Box => { printl('default') return Box[[1] 'made'] }
let touch = (box:Box=make()):>int64 => {
    box.items.push(9)
    box.label = 'changed'
    return box.items.length
}
let identity = (box:Box=make()):>Box => box
let add = (items:set<int64>=set[]):>set<int64> => { items.add(7) return items }
let map = (... items:dict<int64 string>=[1 -> 'one']):>dict<int64 string> => {
    items[2] = 'two'
    return items
}
let noise = ():>void => { let words:array<int64 length=256> = [SCRATCH] words[0]=99 }
let main = ():>int64 => {
    let caller = Box[[4] 'caller']
    printl(touch(caller))
    printl(caller.items.length)
    printl(caller.label)
    printl(touch())
    printl(touch())
    let saved = identity()
    noise()
    printl(saved.label)
    printl(saved.items.length)
    let first = add()
    first.add(8)
    let second = add()
    printl(8 in? second)
    let original:dict<int64 string>=[3 -> 'three']
    let supplied=map(items=original)
    printl(2 in? original)
    printl(2 in? supplied)
    let defaulted=map()
    noise()
    printl(defaulted.get(1 default='missing'))
    printl(defaulted.get(2 default='missing'))
    return 0
}
'''
    source = source.replace('SCRATCH', ' '.join(['0'] * 256))
    output = tmp_path / 'object_defaults.udewy'
    output.write_text(codegen(SrcFile(None, source)))
    assert entry_point(output, [], EntryPointOptions(compile_only=True)) == 0
    result = subprocess.run([cache_artifact(output).resolve()], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        '2', '1', 'caller', 'default', '2', 'default', '2', 'default',
        'made', '1', 'false', 'false', 'true', 'one', 'two',
    ]
