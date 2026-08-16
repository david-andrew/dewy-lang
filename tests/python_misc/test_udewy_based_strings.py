from pathlib import Path
from re import MULTILINE, findall

import pytest

from udewy import p0, t1
from udewy.backend.c import CBackend


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def parse_c(src: str) -> tuple[str, CBackend]:
    backend = CBackend()
    code = p0.parse(t1.tokenize(src), src, backend)
    return code, backend


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        ('0b""', b""),
        ('0x""', b""),
        ('0b"10000001"', b"\x81"),
        ('0x"1234"', b"\x12\x34"),
        ('0b"1"', b"\x80"),
        ('0b"10101"', b"\xa8"),
        ('0x"f"', b"\xf0"),
        ('0x"123"', b"\x12\x30"),
    ],
)
def test_based_string_packing_and_resulting_length(literal: str, expected: bytes) -> None:
    token = t1.tokenize(literal)[0]

    assert token.kind == t1.Kind.TK_BASED_STRING
    length = token.value
    assert isinstance(length, int)
    packed = p0.decode_based_string_literal(literal, token.location, length)
    assert packed == expected
    assert len(packed) == len(expected)


def test_based_string_ignores_separators_comments_and_newlines() -> None:
    literal = '''0x"12 _ # ignored ff and quote "
        34
        # another comment
        5"'''
    token = t1.tokenize(literal)[0]

    length = token.value
    assert isinstance(length, int)
    assert p0.decode_based_string_literal(literal, token.location, length) == b"\x12\x34\x50"


def test_python_and_bootstrap_token_kind_order_matches() -> None:
    bootstrap_t1 = (REPO_ROOT / "udewy" / "bootstrap" / "t1.udewy").read_text()
    bootstrap_values = {
        name: int(value)
        for name, value in findall(
            r"^const (TK_[A-Z_]+):int\s*=\s*(\d+)",
            bootstrap_t1,
            flags=MULTILINE,
        )
    }

    for kind in t1.Kind:
        bootstrap_name = {
            "_TK_COLON": "TK_COLON_TMP",
            "_TK_FN_COLON": "TK_FN_COLON_TMP",
        }.get(kind.name, kind.name)
        assert bootstrap_values[bootstrap_name] == kind.value


@pytest.mark.parametrize(
    ("literal", "base", "digit"),
    [
        ('0b"2"', 2, "2"),
        ('0b"a"', 2, "a"),
        ('0x"g"', 16, "g"),
        ('0x"-"', 16, "-"),
    ],
)
def test_based_string_rejects_invalid_digits(literal: str, base: int, digit: str) -> None:
    with pytest.raises(SyntaxError, match=rf"invalid base-{base} string digit {digit!r}"):
        t1.tokenize(literal)


@pytest.mark.parametrize("literal", ['0b"101', '0x"12 # comment'])
def test_based_string_rejects_unterminated_literals(literal: str) -> None:
    with pytest.raises(SyntaxError, match="unterminated based string"):
        t1.tokenize(literal)


def test_based_strings_work_as_local_global_and_stable_values() -> None:
    src = '''
const stable:int = 0x"1234"
const stable_alias:int = stable
let global:int = 0b"1"

let main = ():>int => {
    const local:int = 0x"ab"
    const local_alias:int = local
    let direct:int = 0b"01"
    return __load_u8__(stable_alias)
        + __load_u8__(global)
        + __load_u8__(local_alias)
        + __load_u8__(direct)
}
'''

    code, backend = parse_c(src)

    assert list(backend._string_contents.values()) == [
        b"\x12\x34",
        b"\x80",
        b"\xab",
        b"\x40",
    ]
    assert "UINT64_C(0x0000000000000002)" in code
    assert "{ 18, 52 }" in code


def test_runtime_array_atoms_are_rejected() -> None:
    src = '''
let main = ():>int => {
    let values:int = [1 2]
    return 0
}
'''

    with pytest.raises(SyntaxError, match="TK_LEFT_BRACKET"):
        parse_c(src)
