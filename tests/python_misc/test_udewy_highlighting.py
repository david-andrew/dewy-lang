from json import loads
from pathlib import Path
from re import finditer, search

from udewy.third_party.web.generate_highlighted_udewy import DEFAULT_THEME, highlighted_spans


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_based_string_highlighting_uses_mixed_literal_colors() -> None:
    spans = highlighted_spans('0b"10_ # note\n 01"')

    assert spans[0].text == "0b"
    assert spans[0].color == DEFAULT_THEME["numeric_prefix"]
    assert [span.color for span in spans if span.text == '"'] == [
        DEFAULT_THEME["string"],
        DEFAULT_THEME["string"],
    ]
    assert [span.color for span in spans if span.text in {"10", "01"}] == [
        DEFAULT_THEME["number"],
        DEFAULT_THEME["number"],
    ]
    assert next(span.color for span in spans if span.text == "# note") == DEFAULT_THEME["comment"]
    assert next(span.color for span in spans if "_" in span.text) is None


def test_hex_based_string_uses_numeric_prefix_and_digit_colors() -> None:
    spans = highlighted_spans('0x"de_ad"')

    assert spans[0].text == "0x"
    assert spans[0].color == DEFAULT_THEME["numeric_prefix"]
    assert [span.color for span in spans if span.text in {"de", "ad"}] == [
        DEFAULT_THEME["number"],
        DEFAULT_THEME["number"],
    ]


def test_empty_based_string_and_quote_in_comment_highlighting() -> None:
    empty_spans = highlighted_spans('0x""')
    assert [span.text for span in empty_spans] == ["0x", '"', '"']

    spans = highlighted_spans('0b"1 # ignored quote "\n 0"')
    comment = next(span for span in spans if span.text.startswith("#"))
    assert comment.text == '# ignored quote "'
    assert comment.color == DEFAULT_THEME["comment"]
    assert spans[-1].text == '"'
    assert spans[-1].color == DEFAULT_THEME["string"]


def test_textmate_based_string_quotes_use_string_scope() -> None:
    grammar_path = REPO_ROOT / "udewy" / "vscode-udewy" / "syntaxes" / "udewy.tmLanguage.json"
    grammar = loads(grammar_path.read_text())

    for pattern in grammar["repository"]["based-string"]["patterns"]:
        assert pattern["beginCaptures"]["2"]["name"] == "string.quoted.double.udewy"
        assert pattern["endCaptures"]["0"]["name"] == "string.quoted.double.udewy"


def test_textmate_highlights_static_words_as_an_intrinsic() -> None:
    grammar_path = REPO_ROOT / "udewy" / "vscode-udewy" / "syntaxes" / "udewy.tmLanguage.json"
    grammar = loads(grammar_path.read_text())

    assert search(grammar["repository"]["intrinsic"]["match"], "__static_words__")


def test_textmate_type_parameter_closes_before_default_assignment() -> None:
    grammar_path = REPO_ROOT / "udewy" / "vscode-udewy" / "syntaxes" / "udewy.tmLanguage.json"
    grammar = loads(grammar_path.read_text())
    end_pattern = grammar["repository"]["type-parameter"]["end"]

    function_default = "<():>int64>=forty_two"
    nested_default = "<array<int64 length=2>>=[0 2]"

    assert [match.start() for match in finditer(end_pattern, function_default)] == [
        function_default.index(">=")
    ]
    assert [match.start() for match in finditer(end_pattern, nested_default)] == [
        nested_default.index(">>"),
        nested_default.index(">=")
    ]


def test_textmate_type_parameter_does_not_close_on_comparison_operators() -> None:
    grammar_path = REPO_ROOT / "udewy" / "vscode-udewy" / "syntaxes" / "udewy.tmLanguage.json"
    grammar = loads(grammar_path.read_text())
    end_pattern = grammar["repository"]["type-parameter"]["end"]

    greater = "<i>?0>"
    greater_or_equal = "<i>=?0>"

    assert [match.start() for match in finditer(end_pattern, greater)] == [len(greater) - 1]
    assert [match.start() for match in finditer(end_pattern, greater_or_equal)] == [
        len(greater_or_equal) - 1
    ]
