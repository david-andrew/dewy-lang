"""Local functions reading enclosing locals lower by lambda lifting."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import NotImplementedYet


def test_captured_values_become_trailing_parameters_at_every_call() -> None:
    emitted = codegen(SrcFile(None, """
let main = ():>int64 => {
    let base:int64 = 10
    let scale = (v:int64):>int64 => v * base
    let twice = (v:int64):>int64 => scale(v) + scale(v)
    return twice(2)
}
"""))
    assert 'let scale = (v:int64 base:int64):>int64' in emitted
    assert 'let twice = (v:int64 base:int64):>int64' in emitted   # transitive: twice passes base on
    assert 'scale(v base)' in emitted and 'twice(2 base)' in emitted


def test_writes_to_captured_bindings_are_rejected() -> None:
    with pytest.raises(NotImplementedYet, match='writing to `count`, which belongs to an enclosing function'):
        codegen(SrcFile(None, "let main = ():>int64 => {\n    let count:int64 = 0\n    let bump = ():>void => { count += 1 }\n    bump()\n    return count\n}\n"))
    with pytest.raises(NotImplementedYet, match='writing to `xs`'):
        codegen(SrcFile(None, "let main = ():>int64 => {\n    let xs:array<int64> = []\n    let grow = ():>void => xs.push(1)\n    grow()\n    return xs.length\n}\n"))


def test_capturing_functions_cannot_escape_yet() -> None:
    with pytest.raises(NotImplementedYet, match='a capturing function used as a value'):
        codegen(SrcFile(None, """
let apply = (f:<(v:int64):>int64> v:int64):>int64 => f(v)
let main = ():>int64 => {
    let base:int64 = 10
    let scale = (v:int64):>int64 => v * base
    return apply(@scale 2)
}
"""))
    with pytest.raises(NotImplementedYet, match='a capturing function used as a value'):
        codegen(SrcFile(None, """
let apply = (f:<(v:int64):>int64> v:int64):>int64 => f(v)
let main = ():>int64 => {
    let base:int64 = 10
    return apply((v:int64):>int64 => v * base, 2)
}
""".replace(", 2", " 2")))


def test_non_capturing_local_functions_are_unchanged() -> None:
    emitted = codegen(SrcFile(None, "let main = ():>int64 => {\n    let double = (v:int64):>int64 => v * 2\n    return double(21)\n}\n"))
    assert 'let double = (v:int64):>int64' in emitted
