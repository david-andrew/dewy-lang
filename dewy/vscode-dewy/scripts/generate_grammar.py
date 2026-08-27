"""Generate syntaxes/dewy.tmLanguage.json from the compiler's lexical tables.

The identifier character classes come straight from `dewy.parser.t0`, so the
grammar accepts exactly the identifiers the tokenizer does. Run from the repo
root after changing the tokenizer or this file:

    uv run python dewy/vscode-dewy/scripts/generate_grammar.py

`tests/python_misc/test_dewy_highlighting.py` checks the committed grammar is
the generator's output.
"""
from __future__ import annotations

import json
from pathlib import Path

from dewy.parser import t0

D = "dewy"
OUTPUT = Path(__file__).resolve().parent.parent / "syntaxes" / f"{D}.tmLanguage.json"


def cls(chars: set[str]) -> str:
    return "".join("\\" + c if c in "\\]^-" else c for c in sorted(chars))


START = cls(t0.start_characters)
CONT = cls(t0.continue_characters | t0.decoration_characters)
DECOR = cls(t0.decoration_characters)
IDENT = f"[{DECOR}]*[{START}][{CONT}]*"
NOT_BEFORE = f"(?<![{CONT}])"  # not glued to a preceding identifier character
NOT_AFTER = f"(?![{CONT}])"
BASE_PREFIX = "0[bBtTqQsSoOdDzZxXuUrRgG]"
NUMBER_PREFIX = "0[bBtTqQsSoOdDzZxX]"  # numerals stop at base 16; higher bases are packed strings only


def rule(name: str, match: str, **extra: object) -> dict:
    return {"name": f"{name}.{D}", "match": match, **extra}


def quoted(kind: str, quote: str, *, raw: bool = False, prefix: str | None = None, prefix_scope: str | None = None, interpolate: bool = True) -> dict:
    """One string rule; `quote` is the delimiter run: `"`, `'`, `\"\"\"`, or `'''`."""
    q = quote.replace('"', '\\"')
    if prefix:
        begin = f"({prefix})({q})"
        begin_captures = {"1": {"name": prefix_scope}, "2": {"name": f"punctuation.definition.string.begin.{D}"}}
    else:
        # no lookbehind: `printl"{x}"` glues the quote to the call name
        begin = f"({q})"
        begin_captures = {"1": {"name": f"punctuation.definition.string.begin.{D}"}}
    patterns: list[dict] = []
    if not raw:
        patterns.append({"include": "#string-escape"})
        if interpolate:
            patterns.append({"include": "#string-interpolation"})
    return {
        "name": f"string.quoted.{kind}.{D}",
        "begin": begin,
        "beginCaptures": begin_captures,
        "end": q,
        "endCaptures": {"0": {"name": f"punctuation.definition.string.end.{D}"}},
        "patterns": patterns,
    }


def based_string(quote: str) -> dict:
    q = quote.replace('"', '\\"')
    return {
        "name": f"meta.based-string.{D}",
        "begin": f"{NOT_BEFORE}({BASE_PREFIX})({q})",
        "beginCaptures": {"1": {"name": f"storage.type.numeric.prefix.{D}"}, "2": {"name": f"string.quoted.based.{D}"}},
        "end": q,
        "endCaptures": {"0": {"name": f"string.quoted.based.{D}"}},
        "patterns": [{"include": "#comment"}, rule("constant.numeric.based", "[0-9A-Za-z+/=_-]+")],
    }


RAW = f"storage.type.string.raw.{D}"
TEMPLATE = f"storage.type.string.template.{D}"
PATH = f"entity.name.function.call.{D}"
TYPE_END = "(?!\\s*[<\\[]|\\s*[|&]\\s*)"  # a type expression continues only through `<`, `[`, `|`, `&`
TYPE_INTRO = "(?:(:>)|(:)(?![=:>?]))"  # `:>` is the return-type arrow, `:` the annotation separator
TYPE_INTRO_CAPTURES = {
    "1": {"name": f"keyword.operator.arrow.return-type.{D}"},
    "2": {"name": f"punctuation.separator.type.{D}"},
}


def group(kind: str, open_: str, close: str) -> dict:
    """A balanced bracket group whose contents are ordinary Dewy."""
    return {
        "name": f"meta.group.{kind}.{D}",
        "begin": open_,
        "beginCaptures": {"0": {"name": f"punctuation.section.{kind}.begin.{D}"}},
        "end": close,
        "endCaptures": {"0": {"name": f"punctuation.section.{kind}.end.{D}"}},
        "patterns": [{"include": "#group"}, {"include": "$self"}],
    }

GRAMMAR = {
    "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
    "name": "Dewy",
    "scopeName": f"source.{D}",
    "patterns": [
        {"include": "#comment"},
        {"include": "#heredoc-string"},
        {"include": "#rest-of-file-string"},
        {"include": "#based-string"},
        {"include": "#based-block"},
        {"include": "#raw-string"},
        {"include": "#prefixed-string"},
        {"include": "#string"},
        {"include": "#number"},
        {"include": "#metatag"},
        {"include": "#constant"},
        {"include": "#generic-parameters"},
        {"include": "#type-annotation"},
        {"include": "#function-definition"},
        {"include": "#keyword"},
        {"include": "#comparison-word"},
        {"include": "#word-operator"},
        {"include": "#builtin-type"},
        {"include": "#function-handle"},
        {"include": "#function-call"},
        {"include": "#operator"},
        {"include": "#identifier"},
        {"include": "#punctuation"},
    ],
    "repository": {
        "comment": {"patterns": [{"include": "#block-comment"}, rule("comment.line.number-sign", "#.*$")]},
        "block-comment": {
            "name": f"comment.block.{D}",
            "begin": "#\\{",
            "end": "\\}#",
            "patterns": [{"include": "#block-comment"}],
        },
        "string-escape": {
            "patterns": [
                rule("invalid.illegal.hex-escape", "\\\\[xX][0-9A-Fa-f]{0,2}"),
                rule("constant.character.escape.unicode", "\\\\[uU](?:\\{[0-9A-Fa-f]+\\}|[0-9A-Fa-f]{4})"),
                rule("constant.character.escape.line-continuation", "\\\\$"),
                rule("constant.character.escape", "\\\\."),
            ]
        },
        "string-interpolation": {
            "patterns": [
                {
                    # `meta.embedded` resets the standard token type from "string"
                    # to code, so bracket-pair colorization treats the braces and
                    # everything inside them as ordinary brackets
                    "name": f"meta.embedded.line.{D}",
                    "begin": "\\{",
                    "beginCaptures": {"0": {"name": f"punctuation.definition.template-expression.begin.{D}"}},
                    "end": "\\}",
                    "endCaptures": {"0": {"name": f"punctuation.definition.template-expression.end.{D}"}},
                    "patterns": [{"include": "#brace-group"}, {"include": "$self"}],
                }
            ]
        },
        "brace-group": group("braces", "\\{", "\\}"),
        "group": {
            "patterns": [
                group("parens", "\\(", "\\)"),
                group("brackets", "\\[", "\\]"),
                group("braces", "\\{", "\\}"),
            ]
        },
        "string": {
            "patterns": [
                quoted("triple.double", '"""'),
                quoted("triple.single", "'''"),
                quoted("double", '"'),
                quoted("single", "'"),
            ]
        },
        "raw-string": {
            "patterns": [
                quoted("raw.triple.double", '"""', raw=True, prefix="r", prefix_scope=RAW),
                quoted("raw.triple.single", "'''", raw=True, prefix="r", prefix_scope=RAW),
                quoted("raw.double", '"', raw=True, prefix="r", prefix_scope=RAW),
                quoted("raw.single", "'", raw=True, prefix="r", prefix_scope=RAW),
            ]
        },
        "prefixed-string": {
            "patterns": [
                quoted("template.triple.double", '"""', prefix="t", prefix_scope=TEMPLATE),
                quoted("template.triple.single", "'''", prefix="t", prefix_scope=TEMPLATE),
                quoted("template.double", '"', prefix="t", prefix_scope=TEMPLATE),
                quoted("template.single", "'", prefix="t", prefix_scope=TEMPLATE),
                quoted("path.double", '"', prefix="p", prefix_scope=PATH, interpolate=False),
                quoted("path.single", "'", prefix="p", prefix_scope=PATH, interpolate=False),
            ]
        },
        "heredoc-string": {
            "name": f"string.quoted.heredoc.{D}",
            "begin": "(\\$)([rt]?)([\"'])([^\"'\\s]+)\\3",
            "beginCaptures": {
                "1": {"name": f"punctuation.definition.string.begin.{D}"},
                "2": {"name": f"storage.type.string.prefix.{D}"},
                "3": {"name": f"punctuation.definition.string.begin.{D}"},
                "4": {"name": f"entity.name.tag.heredoc-delimiter.{D}"},
            },
            "end": "\\4",
            "endCaptures": {"0": {"name": f"entity.name.tag.heredoc-delimiter.{D}"}},
            "patterns": [{"include": "#string-escape"}, {"include": "#string-interpolation"}],
        },
        "rest-of-file-string": {
            "name": f"string.quoted.rest-of-file.{D}",
            "begin": "(\\$)([rt]?)(\"\"\"|''')",
            "beginCaptures": {
                "1": {"name": f"punctuation.definition.string.begin.{D}"},
                "2": {"name": f"storage.type.string.prefix.{D}"},
                "3": {"name": f"punctuation.definition.string.begin.{D}"},
            },
            "end": "\\b\\B",
            "patterns": [{"include": "#string-escape"}, {"include": "#string-interpolation"}],
        },
        "based-string": {"patterns": [based_string(q) for q in ('"""', "'''", '"', "'")]},
        "based-block": {
            "match": f"{NOT_BEFORE}({BASE_PREFIX})(\\[)",
            "captures": {"1": {"name": f"storage.type.numeric.prefix.{D}"}, "2": {"name": f"punctuation.section.brackets.begin.{D}"}},
        },
        "number": {
            "patterns": [
                {
                    "match": f"{NOT_BEFORE}({NUMBER_PREFIX})([0-9A-Za-z_]+)",
                    "captures": {"1": {"name": f"storage.type.numeric.prefix.{D}"}, "2": {"name": f"constant.numeric.based.{D}"}},
                },
                rule("constant.numeric.decimal", f"{NOT_BEFORE}(?<!\\.)[0-9][0-9_]*(?:\\.[0-9][0-9_]*)?(?:[eE][+-]?[0-9][0-9_]*)?"),
            ]
        },
        "metatag": {
            "match": "(\\$)([A-Za-z_][A-Za-z0-9_]*)?",
            "captures": {"1": {"name": f"punctuation.definition.metatag.{D}"}, "2": {"name": f"keyword.other.metatag.{D}"}},
        },
        "constant": {
            "patterns": [
                rule("constant.language.boolean", "\\b(true|false)\\b"),
                rule("constant.language.void", "\\bvoid\\b"),
                rule("constant.language.undefined", "\\bundefined\\b"),
                rule("constant.language.end", "\\bend\\b"),
                rule("constant.language.symbolic", "[∞∅]"),
            ]
        },
        "keyword": {
            "patterns": [
                rule("keyword.control", "\\b(if|else|loop|match|return|yield|break|continue)\\b"),
                rule("keyword.declaration", "\\b(let|const|local_const|overload_only)\\b"),
                rule("keyword.control.import", "\\b(import|from)\\b"),
            ]
        },
        "comparison-word": {"patterns": [rule("keyword.other.word-operator.comparison", "\\b(?:in|is|isnt)\\?|\\bnot=\\?")]},
        "word-operator": {"patterns": [rule("keyword.other.word-operator", "\\b(and|or|xor|nand|nor|xnor|not|as|in|of|transmute|or_throw)\\b")]},
        "builtin-type": {
            "patterns": [
                rule("support.type.primitive", "\\b(int|uint|int8|int16|int32|int64|uint8|uint16|uint32|uint64|bool|string|char|rational|fixed|bigint|type)\\b"),
                rule("support.type.container", "\\b(array|dict|set)\\b(?=\\s*<)"),
                rule("support.type.dimension", "\\b(Time|Length|Mass|Current|Temperature|Amount|Luminosity|Angle)\\b"),
            ]
        },
        "type-annotation": {
            "patterns": [
                {
                    "begin": f"{TYPE_INTRO}\\s*(?=[<\\[])",
                    "beginCaptures": TYPE_INTRO_CAPTURES,
                    "end": TYPE_END,
                    "applyEndPatternLast": True,
                    "patterns": [{"include": "#type-expression"}],
                },
                {
                    "begin": f"{TYPE_INTRO}\\s*({IDENT})",
                    "beginCaptures": {**TYPE_INTRO_CAPTURES, "3": {"name": f"entity.name.type.{D}"}},
                    "end": TYPE_END,
                    "applyEndPatternLast": True,
                    "patterns": [{"include": "#type-expression"}],
                },
            ]
        },
        "type-expression": {
            "patterns": [
                {"include": "#type-parameter"},
                {"include": "#bracketed-type"},
                {
                    "match": f"([|&])\\s*({IDENT})?",
                    "captures": {"1": {"name": f"keyword.operator.type.{D}"}, "2": {"name": f"entity.name.type.{D}"}},
                },
            ]
        },
        "generic-parameters": {
            # `<T U of Bound>` before a parameter list or object type: the type
            # parameters of a generic function or alias. Names and bounds are
            # types, `of` is a word operator, the angles are a bracket pair.
            "name": f"meta.generic-parameters.{D}",
            "begin": "<(?=[^<>\\n]*>\\s*[(\\[])",
            "beginCaptures": {"0": {"name": f"punctuation.section.angle.begin.{D}"}},
            "end": ">",
            "endCaptures": {"0": {"name": f"punctuation.section.angle.end.{D}"}},
            "patterns": [
                {"include": "#comment"},
                rule("keyword.other.word-operator", "\\bof\\b"),
                {"include": "#type-parameter"},
                {"include": "#builtin-type"},
                rule("entity.name.type", f"{NOT_BEFORE}{IDENT}{NOT_AFTER}"),
                {"include": "#punctuation"},
            ],
        },
        "type-parameter": {
            # `<…>` is a bracket group: bare names are types, `name=` and `name:`
            # are ordinary identifiers, and the right-hand side of `=` is an
            # ordinary expression
            "name": f"meta.type-parameter.{D}",
            "begin": "<(?![?=<|-])",
            "beginCaptures": {"0": {"name": f"punctuation.section.angle.begin.{D}"}},
            "end": "(?<![:-])>(?!\\?|=\\?)",
            "endCaptures": {"0": {"name": f"punctuation.section.angle.end.{D}"}},
            "patterns": [
                {"include": "#comment"},
                rule("variable.parameter", f"{IDENT}(?=\\s*[:=](?![=>?:]))"),
                {
                    "name": f"meta.type-parameter.value.{D}",
                    "begin": "=(?![=>?])",
                    "beginCaptures": {"0": {"name": f"keyword.operator.assignment.{D}"}},
                    "end": "(?=[\\s>\\])])",
                    "patterns": [{"include": "#group"}, {"include": "$self"}],
                },
                rule("keyword.other.word-operator", "\\bof\\b"),
                {"include": "#type-annotation"},
                {"include": "#type-parameter"},
                {"include": "#bracketed-type"},
                {"include": "#string"},
                {"include": "#number"},
                {"include": "#constant"},
                {"include": "#builtin-type"},
                {"include": "#operator"},
                rule("entity.name.type", f"{NOT_BEFORE}{IDENT}{NOT_AFTER}"),
                {"include": "#punctuation"},
            ],
        },
        "bracketed-type": {
            # `[name:T …]` object types: member names are ordinary identifiers and
            # their annotations are types, exactly as in a value-level literal
            "name": f"meta.bracketed-type.{D}",
            "begin": "\\[",
            "beginCaptures": {"0": {"name": f"punctuation.section.brackets.begin.{D}"}},
            "end": "\\]",
            "endCaptures": {"0": {"name": f"punctuation.section.brackets.end.{D}"}},
            "patterns": [{"include": "#bracketed-type"}, {"include": "#group"}, {"include": "$self"}],
        },
        "function-definition": {
            "match": f"({IDENT})(?=\\s*=\\s*\\([^#\\n]*\\)\\s*(?::>[^#\\n=]*)?=>)",
            "captures": {"1": {"name": f"entity.name.function.{D}"}},
        },
        "function-handle": {
            "match": f"(@)({IDENT})",
            "captures": {"1": {"name": f"storage.modifier.reference.{D}"}, "2": {"name": f"variable.function.{D}"}},
        },
        "function-call": {
            "match": f"{NOT_BEFORE}({IDENT})(?=\\(|[\"'])",
            "captures": {"1": {"name": f"entity.name.function.call.{D}"}},
        },
        "operator": {
            "patterns": [
                rule("keyword.operator.comparison", "<=>|>=\\?|<=\\?|>\\?|<\\?|=\\?"),
                rule("keyword.operator.assignment.compound", "\\+=|-=|\\*=|//=|/=|%=|\\^=|<<=|>>="),
                rule("keyword.operator.pipe", "\\|>|<\\|"),
                rule("keyword.operator.arrow", "=>|<->|->|:>"),
                rule("keyword.operator.binding", "::|:="),
                rule("keyword.operator.range", "\\.\\.\\.|\\.\\."),
                rule("keyword.operator.optional", "\\?\\?|@\\?|\\?"),
                # `@` selects a function value or a place: modifier-colored so it
                # does not vanish among the punctuation it sits next to
                rule("storage.modifier.reference", "@"),
                rule("keyword.operator.shift", "<<<|>>>|<<!|!>>|<<|>>"),
                rule("keyword.operator.arithmetic", "//|[+\\-*/%^\\\\]"),
                rule("keyword.operator.bitwise", "[|&~`]"),
                rule("keyword.operator.assignment", "(?<![=!<>:?])=(?![=>?])"),
                rule("punctuation.separator.type", ":"),
                rule("punctuation.accessor", "\\."),
            ]
        },
        "identifier": {"name": f"variable.other.{D}", "match": f"{NOT_BEFORE}{IDENT}{NOT_AFTER}"},
        "punctuation": {
            "patterns": [
                rule("punctuation.section.braces.begin", "\\{"),
                rule("punctuation.section.braces.end", "\\}"),
                rule("punctuation.section.brackets.begin", "\\["),
                rule("punctuation.section.brackets.end", "\\]"),
                rule("punctuation.section.parens.begin", "\\("),
                rule("punctuation.section.parens.end", "\\)"),
                rule("punctuation.terminator", ";"),
                rule("punctuation.separator", ","),
                rule("punctuation.separator.angle", "[<>]"),
            ]
        },
    },
}


def render() -> str:
    return json.dumps(GRAMMAR, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render())
    print(f"wrote {OUTPUT}")
