"""Regex-level checks of the Dewy TextMate grammar (dewy/vscode-dewy).

There is no TextMate engine in the test environment, so these tests exercise
the individual patterns with Python's `re` and cross-check the keyword and
operator tables against the parser's own definitions so the grammar cannot
silently drift from the language.
"""
from importlib import import_module
from json import loads
from pathlib import Path
from re import compile as compile_regex
from re import error as RegexError
from re import fullmatch, match, search

import pytest

from dewy.parser import t0, t1, t2

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRAMMAR_PATH = REPO_ROOT / "dewy" / "vscode-dewy" / "syntaxes" / "dewy.tmLanguage.json"
GRAMMAR = loads(GRAMMAR_PATH.read_text())
REPOSITORY = GRAMMAR["repository"]


def _patterns(node: object):
    """Every (key, regex) pair in the grammar, depth first."""
    if isinstance(node, dict):
        for key in ("match", "begin", "end"):
            if key in node:
                yield key, node[key]
        for value in node.values():
            yield from _patterns(value)
    elif isinstance(node, list):
        for item in node:
            yield from _patterns(item)


def _all_rules(node: object):
    if isinstance(node, dict):
        if "match" in node or "begin" in node:
            yield node
        for value in node.values():
            yield from _all_rules(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_rules(item)


def _repo(name: str) -> dict:
    return REPOSITORY[name]


def _rule(name: str, index: int = 0) -> dict:
    node = _repo(name)
    return node["patterns"][index] if "patterns" in node else node


def test_every_pattern_is_a_valid_regex() -> None:
    for key, pattern in _patterns(GRAMMAR):
        if key == "end" and "\\" in pattern and any(f"\\{n}" in pattern for n in "123456789"):
            continue  # backreferences into `begin` only resolve inside the engine
        try:
            compile_regex(pattern)
        except RegexError as error:  # pragma: no cover - the message is the point
            pytest.fail(f"{key} pattern {pattern!r} does not compile: {error}")


def test_every_scope_name_ends_with_dewy() -> None:
    for rule in _all_rules(GRAMMAR):
        for scope_holder in (rule, *rule.get("captures", {}).values(), *rule.get("beginCaptures", {}).values(), *rule.get("endCaptures", {}).values()):
            name = scope_holder.get("name")
            if name is not None:
                assert name.endswith(".dewy"), name
        if "contentName" in rule:
            assert rule["contentName"].endswith(".dewy")


def test_package_declares_the_grammar_and_language() -> None:
    package = loads((GRAMMAR_PATH.parent.parent / "package.json").read_text())
    language = package["contributes"]["languages"][0]
    grammar = package["contributes"]["grammars"][0]
    assert language["id"] == "dewy" and ".dewy" in language["extensions"]
    assert grammar["scopeName"] == GRAMMAR["scopeName"] == "source.dewy"
    assert (GRAMMAR_PATH.parent.parent / grammar["path"]).resolve() == GRAMMAR_PATH
    for relative in package["files"]:
        assert (GRAMMAR_PATH.parent.parent / relative).exists(), relative


def test_keyword_patterns_cover_exactly_the_parser_keywords() -> None:
    patterns = [rule["match"] for rule in _repo("keyword")["patterns"]]
    for keyword in t1.keywords:
        assert any(fullmatch(pattern, keyword) for pattern in patterns), keyword
    highlighted = set()
    for pattern in patterns:
        alternatives = pattern[pattern.index("(") + 1 : pattern.index(")")]
        highlighted.update(alternatives.split("|"))
    assert highlighted == t1.keywords


def test_word_operators_match_the_parser_tables() -> None:
    pattern = _rule("word-operator")["match"]
    word_ops = {op for op in t2.binary_ops | t2.prefix_ops | t2.postfix_ops if op.replace('_', '').isalpha()}
    for op in word_ops:
        assert fullmatch(pattern, op), op
    comparison = _rule("comparison-word")["match"]
    for op in ("in?", "is?", "isnt?"):
        assert op in t2.binary_ops and fullmatch(comparison, op), op
    assert fullmatch(comparison, "not=?")


def test_identifier_pattern_follows_the_tokenizer_repertoire() -> None:
    pattern = _repo("identifier")["match"]
    for identifier in ("x", "_bigint_trim", "x₁", "ℝ³", "v′", "extract_ints!", "°", "π", "ʰello", "𝔼", "Δt"):
        assert fullmatch(pattern, identifier), identifier
        assert t0.Identifier.eat(identifier, None) == len(identifier), identifier
    for not_identifier in ("1abc", "-", "é", "", "₁"):
        assert not fullmatch(pattern, not_identifier), not_identifier


def test_number_patterns_match_the_literal_forms() -> None:
    based, decimal = (rule["match"] for rule in _repo("number")["patterns"])
    for literal in ("0b101010", "0t1120", "0q222", "0s110", "0o52", "0d42", "0z36", "0x2a", "0xDEAD_BEEF", "0B1"):
        assert fullmatch(based, literal), literal
    for literal in ("42", "1_000_000", "9.8", "1.25e2", "5e-1", "0", "1e10"):
        assert fullmatch(decimal, literal), literal
    # a range `1..5` is two numbers around `..`, never `1.` and `.5`
    assert match(decimal, "1..5").group(0) == "1"
    assert match(decimal, "2e") .group(0) == "2"
    assert not match(decimal, ".5")


def test_based_strings_use_the_string_scope_for_their_quotes() -> None:
    for rule in _repo("based-string")["patterns"]:
        assert rule["beginCaptures"]["2"]["name"] == "string.quoted.based.dewy"
        assert rule["endCaptures"]["0"]["name"] == "string.quoted.based.dewy"
    begin = _repo("based-string")["patterns"][-2]["begin"]
    assert match(begin, '0x"deadbeef"')
    assert match(begin, '0g"SGVsbG8="')
    assert not match(begin, 'x0x"1"')


def test_string_escapes_flag_hex_escapes_and_accept_unicode() -> None:
    illegal, unicode_escape, continuation, escape = (rule["match"] for rule in _repo("string-escape")["patterns"])
    assert fullmatch(illegal, "\\x41")
    assert fullmatch(unicode_escape, "\\u00e9") and fullmatch(unicode_escape, "\\u{1F600}")
    assert fullmatch(continuation, "\\")
    assert fullmatch(escape, "\\{") and fullmatch(escape, "\\n")


def test_heredoc_begin_captures_its_delimiter() -> None:
    begin = _repo("heredoc-string")["begin"]
    found = match(begin, '$"EOF" body')
    assert found and found.group(4) == "EOF"
    assert _repo("heredoc-string")["end"] == "\\4"
    assert match(begin, "$r'---'").group(2) == "r"
    assert not match(begin, '$"""')


def test_type_parameter_closes_before_defaults_but_not_on_comparisons() -> None:
    end_pattern = _repo("type-parameter")["end"]
    function_default = "<():>int64>=@forty_two"
    nested_default = "<array<int64 length=2>>=[0 2]"
    assert [m.start() for m in compile_regex(end_pattern).finditer(function_default)] == [function_default.index(">=")]
    assert [m.start() for m in compile_regex(end_pattern).finditer(nested_default)] == [
        nested_default.index(">>"),
        nested_default.index(">="),
    ]
    for expression in ("<i>?0>", "<i>=?0>"):
        assert [m.start() for m in compile_regex(end_pattern).finditer(expression)] == [len(expression) - 1]


def test_type_annotations_start_on_colon_but_not_on_binding_operators() -> None:
    bracket_begin, named_begin = (rule["begin"] for rule in _repo("type-annotation")["patterns"])
    assert match(named_begin, ":int64").group(2) == ":"
    assert match(named_begin, ":>int64").group(1) == ":>"
    captures = _repo("type-annotation")["patterns"][1]["beginCaptures"]
    assert captures["1"]["name"] == "keyword.operator.arrow.return-type.dewy"
    assert captures["2"]["name"] == "punctuation.separator.type.dewy"
    assert match(bracket_begin, ":<(x:int64):>int64>")
    assert match(bracket_begin, ":[a:int b:int]")
    for not_annotation in (":=", "::", ":>=", ":?"):
        assert not match(named_begin, not_annotation) and not match(bracket_begin, not_annotation), not_annotation


def test_function_definition_and_handle_patterns() -> None:
    definition = _repo("function-definition")["match"]
    assert match(definition, "double = (x:int64):>int64 => x * 2").group(1) == "double"
    assert match(definition, "main = () => {")
    assert not match(definition, "total = (a + b) * c")
    handle = _repo("function-handle")["match"]
    assert match(handle, "@_print_bigint").group(2) == "_print_bigint"
    assert _repo("function-handle")["captures"]["1"]["name"] == "storage.modifier.reference.dewy"
    bare_at = next(rule for rule in _repo("operator")["patterns"] if rule["match"] == "@")
    assert bare_at["name"] == "storage.modifier.reference.dewy"
    call = _repo("function-call")["match"]
    assert match(call, 'printl"{x}"').group(1) == "printl"
    assert match(call, "sum(1 2)").group(1) == "sum"
    assert not match(call, "xs[0]")


def test_operators_cover_the_parser_symbol_table() -> None:
    operator_patterns = [rule["match"] for rule in _repo("operator")["patterns"]]
    other = [
        _rule("comparison-word")["match"],
        _repo("metatag")["match"],
        *[rule["match"] for rule in _repo("punctuation")["patterns"]],
        _rule("constant", 4)["match"],
    ]
    for symbol in t0.symbols + t0.shift_operators:
        assert any(fullmatch(pattern, symbol) for pattern in operator_patterns + other), symbol


def test_comments_nest_and_line_comments_do_not_swallow_block_openers() -> None:
    block = _repo("block-comment")
    assert block["begin"] == "#\\{" and block["end"] == "\\}#"
    assert {"include": "#block-comment"} in block["patterns"]
    assert _repo("comment")["patterns"][0] == {"include": "#block-comment"}
    assert search(_repo("comment")["patterns"][1]["match"], "let x = 1 # note")


def test_committed_grammar_is_the_generator_output() -> None:
    import sys

    sys.path.insert(0, str(GRAMMAR_PATH.parent.parent / "scripts"))
    generator = import_module("generate_grammar")
    assert GRAMMAR_PATH.read_text() == generator.render()


def test_every_pattern_scans_the_fixture_sources() -> None:
    """Every regex must scan real Dewy sources without error (or pathological time)."""
    sources = [path.read_text() for path in sorted((REPO_ROOT / "dewy" / "tests").glob("*.dewy"))]
    sources += [path.read_text() for path in sorted((REPO_ROOT / "library").rglob("*.dewy"))]
    assert sources
    for key, pattern in _patterns(GRAMMAR):
        if key == "end" and any(f"\\{n}" in pattern for n in "123456789"):
            continue
        regex = compile_regex(pattern)
        for source in sources:
            for line in source.splitlines():
                for _ in regex.finditer(line):
                    pass


def test_strings_may_be_glued_to_a_call_name() -> None:
    double = _repo("string")["patterns"][2]
    assert search(double["begin"], 'printl"{scaled} {shifted}"').start() == len("printl")
    call = _repo("function-call")["match"]
    assert match(call, 'printl"{scaled}"').end() == len("printl")


def test_range_delimiters_balance_across_kinds() -> None:
    """`[0..n)` and `(a..b]` are balanced by the editor itself: an opening
    bracket may pair with either closer, so no `..` heuristic is needed."""
    config = loads((GRAMMAR_PATH.parent.parent / "language-configuration.json").read_text())
    pairs = {tuple(pair) for pair in config["brackets"]}
    assert {("[", "]"), ("(", ")"), ("[", ")"), ("(", "]")} <= pairs
    assert "range-group" not in REPOSITORY
    package = loads((GRAMMAR_PATH.parent.parent / "package.json").read_text())
    unbalanced = package["contributes"]["grammars"][0]["unbalancedBracketScopes"]
    assert "keyword.operator" in unbalanced


def test_type_parameters_are_broken_down() -> None:
    parameter = _repo("type-parameter")
    assert parameter["beginCaptures"]["0"]["name"] == "punctuation.section.angle.begin.dewy"
    assert "contentName" not in parameter
    name_rule, value_rule = parameter["patterns"][1], parameter["patterns"][2]
    assert name_rule["name"] == "variable.parameter.dewy"
    assert match(name_rule["match"], "length=2").group(0) == "length"
    assert match(name_rule["match"], "x:int64").group(0) == "x"
    assert not match(name_rule["match"], "int64 length=2")
    assert not match(name_rule["match"], "f=>1") and not match(name_rule["match"], "a=?b")
    assert match(value_rule["begin"], "=2") and not match(value_rule["begin"], "=>")
    assert compile_regex(value_rule["end"]).search("2 length") .start() == 1
    type_rule = next(rule for rule in parameter["patterns"] if rule.get("name") == "entity.name.type.dewy")
    assert fullmatch(type_rule["match"], "Pair")
    config = loads((GRAMMAR_PATH.parent.parent / "language-configuration.json").read_text())
    assert ["<", ">"] in config["brackets"]
    # VS Code leaves `<>` out of the default colorized set, so it must be explicit
    assert ["<", ">"] in config["colorizedBracketPairs"]
    assert {tuple(pair) for pair in config["brackets"]} == {tuple(pair) for pair in config["colorizedBracketPairs"]}


def test_word_operators_and_interpolation_use_keyword_and_template_scopes() -> None:
    assert _rule("word-operator")["name"] == "keyword.other.word-operator.dewy"
    assert _rule("comparison-word")["name"].startswith("keyword.other.")
    interpolation = _rule("string-interpolation")
    assert interpolation["beginCaptures"]["0"]["name"] == "punctuation.definition.template-expression.begin.dewy"
    assert interpolation["endCaptures"]["0"]["name"] == "punctuation.definition.template-expression.end.dewy"
    # the whole interpolation (braces included) is embedded code, and no scope
    # selector excludes strings wholesale, or brackets inside interpolations
    # would be excluded with them
    assert interpolation["name"] == "meta.embedded.line.dewy" and "contentName" not in interpolation
    package = loads((GRAMMAR_PATH.parent.parent / "package.json").read_text())
    unbalanced = package["contributes"]["grammars"][0]["unbalancedBracketScopes"]
    assert not any(scope.startswith(("string", "comment", "meta")) for scope in unbalanced)


def test_generic_parameter_blocks_are_bracket_groups_of_types() -> None:
    generic = _repo("generic-parameters")
    begin = generic["begin"]
    for source in ("<T>(x:T):>T => x", "<T of int>(a:T b:T):>T => a + b", "<T U>(a:T b:U):>[x:U y:T] => [x=b y=a]", "<T>[value:T]"):
        assert match(begin, source), source
    for source in ("<? 3", "a <b", "<(x:int64):>int64> = @f", "<int64 length=2> = [0 2]"):
        assert not match(begin, source), source
    assert generic["beginCaptures"]["0"]["name"] == "punctuation.section.angle.begin.dewy"
    of_rule = next(rule for rule in generic["patterns"] if rule.get("match") == "\\bof\\b")
    assert of_rule["name"] == "keyword.other.word-operator.dewy"
    type_rule = next(rule for rule in generic["patterns"] if rule.get("name") == "entity.name.type.dewy")
    assert fullmatch(type_rule["match"], "T") and fullmatch(type_rule["match"], "real")


def test_type_blocks_after_assignment_are_type_groups() -> None:
    block = _repo("type-block")
    assert search(block["begin"], 'let Mode:type = <1 | 2 | "fast">')
    assert not search(block["begin"], "if a <? b")
    assert not search(block["begin"], "let fn:<(x:int64):>int64> = @f")
    assert not search(block["begin"], "x = 5")
    assert block["beginCaptures"]["3"]["name"] == "punctuation.section.angle.begin.dewy"
