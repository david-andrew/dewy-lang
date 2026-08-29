"""`$include_bytes(p"…")`: a file's bytes at compile time, embedded by the target."""
import pytest

from dewy.backend.udewy import codegen
from dewy.reporting import SrcFile
from dewy.semantic.errors import UserError
from udewy import t0


def test_udewy_include_bytes_is_a_prelude_directive_with_a_path_literal(tmp_path) -> None:
    (tmp_path / "data.bin").write_bytes(b"abc")
    program = tmp_path / "prog.udewy"
    program.write_text('$include_bytes(p"data.bin") as t\nlet main = ():>int64 => __load_u8__(t + 2)\n')
    loaded = t0.load_program(program)
    assert 'let t:int64 = 0x"616263"' in loaded.source and "$include_bytes" not in loaded.source
    program.write_text('$include_bytes("data.bin") as t\n')
    with pytest.raises(SyntaxError, match="exactly one path literal"):
        t0.load_program(program)
    program.write_text('$include_bytes(p"data.bin")\n')
    with pytest.raises(SyntaxError, match="needs a name"):
        t0.load_program(program)
    program.write_text('$include_bytes(p"missing.bin") as t\n')
    with pytest.raises(SyntaxError, match="no such file"):
        t0.load_program(program)


def test_dewy_include_bytes_is_a_binary_literal_from_a_compile_time_path(tmp_path) -> None:
    (tmp_path / "table.bin").write_bytes(bytes(range(5)))
    source = tmp_path / "main.dewy"
    source.write_text('let t = $include_bytes(p"table.bin")\n$include_bytes(p"table.bin") as u\nlet main = ():>int64 => t.length + u.length + (t[4] transmute int64)\n')
    emitted = codegen(SrcFile.from_path(source))
    assert emitted.startswith(f'$include_bytes(p"{(tmp_path / "table.bin").resolve()}") as __dewy_include_1\n')
    assert emitted.count("$include_bytes(") == 1 and '0x"0001020304"' not in emitted
    with pytest.raises(UserError, match="compile-time path"):
        codegen(SrcFile(None, 'let name:string = "x"\nlet t = $include_bytes(p(name))\nlet main = ():>int64 => 0\n'))
