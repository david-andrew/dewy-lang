"""Drop-at-scope-exit for growable arrays: releases on growth and at every scope exit, only when the arena owns the data."""
from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile


def _emit(source: str) -> str:
    return codegen(SrcFile(None, source))


def test_growth_releases_the_old_buffer_and_marks_ownership() -> None:
    emitted = _emit('let main = ():>int64 => { let xs:array<int64> = []  xs.push(1)  return xs.length }\n')
    body = emitted[emitted.index('let main ='):]
    assert '_arena_release(' in body
    assert body.count('__store_i64__(1 ') >= 1          # owner = 1 after relocation


def test_scope_exits_release_owned_locals() -> None:
    emitted = _emit(
        'let f = (n:int64):>int64 => {\n'
        '    let acc:array<int64> = []\n'
        '    let i:int64 = 0\n'
        '    loop i <? n {\n'
        '        let inner:array<int64> = []\n'
        '        inner.push(i)\n'
        '        if i =? 3 { break }\n'
        '        if i =? 1 { i += 1  continue }\n'
        '        acc.push(inner.length)\n'
        '        i += 1\n'
        '    }\n'
        '    if n >? 100 { return 0 }\n'
        '    return acc.length\n'
        '}\n'
        'let main = ():>int64 => f(5)\n'
    )
    body = emitted[emitted.index('let f ='):emitted.index('let main =')]
    # `break`, `continue`, the early `return`, the final `return` (acc and inner), and the loop body's end
    assert body.count('_arena_release(') >= 6
    # the return value is computed before the releases
    assert body.index('acc + 8') < body.rindex('_arena_release(')


def test_parameters_and_module_arrays_are_not_released() -> None:
    emitted = _emit(
        'let xs:array<int64> = [1 2]\n'
        'let f = (items:array<int64>):>int64 => items.length\n'
        'let main = ():>int64 => f(xs)\n'
    )
    assert '_arena_release(' not in emitted[emitted.index('let f ='):]
