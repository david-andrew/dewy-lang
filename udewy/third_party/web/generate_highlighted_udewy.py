"""
Long term, the goal is to be able to utilize the bootstrap compiler more directly in code for generating syntax highlighting.
It would roughly have the same functionality as this python script, but a udewy program could import t0/t1 and call relevant functions
directly in order to tokenize and perform the highlighting actions based on token type.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from udewy import t0, t1


DEFAULT_THEME: dict[str, str] = {
    "declaration": "#569cd6",
    "keyword": "#c586c0",
    "function": "#dcdcaa",
    "type": "#4ec9b0",
    "string": "#ce9178",
    "number": "#b5cea8",
    "comment": "#6a9955",
    "meta": "#569cd6",
    "punctuation": "#c586c0",
    "brace": "#ffd700",
    "identifier": "#9cdcfe",
    "operator": "#d4d4d4",
}

DECLARATION_KINDS = {
    t1.Kind.TK_LET,
    t1.Kind.TK_CONST,
}

KEYWORD_KINDS = {
    t1.Kind.TK_IF,
    t1.Kind.TK_LOOP,
    t1.Kind.TK_ELSE,
    t1.Kind.TK_RETURN,
    t1.Kind.TK_BREAK,
    t1.Kind.TK_CONTINUE,
    t1.Kind.TK_EXTERN,
    t1.Kind.TK_TRANSMUTE,
    t1.Kind.TK_VOID,
    t1.Kind.TK_AND,
    t1.Kind.TK_OR,
    t1.Kind.TK_XOR,
    t1.Kind.TK_NOT,
}

BRACE_KINDS = {
    t1.Kind.TK_LEFT_BRACE,
    t1.Kind.TK_RIGHT_BRACE,
}

PUNCTUATION_KINDS = {
    t1.Kind.TK_LEFT_PAREN,
    t1.Kind.TK_RIGHT_PAREN,
    t1.Kind.TK_LEFT_BRACKET,
    t1.Kind.TK_RIGHT_BRACKET,
    t1.Kind.TK_EXPR_CALL,
}

OPERATOR_KINDS = {
    t1.Kind.TK_PLUS,
    t1.Kind.TK_MINUS,
    t1.Kind.TK_MUL,
    t1.Kind.TK_IDIV,
    t1.Kind.TK_MOD,
    t1.Kind.TK_EQ,
    t1.Kind.TK_NOT_EQ,
    t1.Kind.TK_GT,
    t1.Kind.TK_GT_EQ,
    t1.Kind.TK_LT,
    t1.Kind.TK_LT_EQ,
    t1.Kind.TK_LEFT_SHIFT,
    t1.Kind.TK_RIGHT_SHIFT,
    t1.Kind.TK_ASSIGN,
    t1.Kind.TK_UPDATE_ASSIGN,
    t1.Kind.TK_FN_ARROW,
    t1.Kind.TK_PIPE,
}

KEYWORD_TOKEN_TEXT = {
    t1.Kind.TK_LET: "let",
    t1.Kind.TK_CONST: "const",
    t1.Kind.TK_IF: "if",
    t1.Kind.TK_LOOP: "loop",
    t1.Kind.TK_ELSE: "else",
    t1.Kind.TK_RETURN: "return",
    t1.Kind.TK_BREAK: "break",
    t1.Kind.TK_CONTINUE: "continue",
    t1.Kind.TK_EXTERN: "extern",
    t1.Kind.TK_TRANSMUTE: "transmute",
    t1.Kind.TK_VOID: "void",
    t1.Kind.TK_AND: "and",
    t1.Kind.TK_OR: "or",
    t1.Kind.TK_XOR: "xor",
    t1.Kind.TK_NOT: "not",
}

SINGLE_CHAR_TOKEN_TEXT = {
    t1.Kind.TK_LEFT_PAREN: "(",
    t1.Kind.TK_RIGHT_PAREN: ")",
    t1.Kind.TK_LEFT_BRACE: "{",
    t1.Kind.TK_RIGHT_BRACE: "}",
    t1.Kind.TK_LEFT_BRACKET: "[",
    t1.Kind.TK_RIGHT_BRACKET: "]",
    t1.Kind.TK_PLUS: "+",
    t1.Kind.TK_MINUS: "-",
    t1.Kind.TK_MUL: "*",
    t1.Kind.TK_MOD: "%",
    t1.Kind.TK_ASSIGN: "=",
    t1.Kind.TK_EXPR_CALL: "(",
}

MULTI_CHAR_TOKEN_TEXT = {
    t1.Kind.TK_IDIV: "//",
    t1.Kind.TK_EQ: "=?",
    t1.Kind.TK_NOT_EQ: "=?",
    t1.Kind.TK_GT: ">?",
    t1.Kind.TK_GT_EQ: ">=?",
    t1.Kind.TK_LT: "<?",
    t1.Kind.TK_LT_EQ: "<=?",
    t1.Kind.TK_LEFT_SHIFT: "<<",
    t1.Kind.TK_RIGHT_SHIFT: ">>",
    t1.Kind.TK_FN_ARROW: "=>",
    t1.Kind.TK_PIPE: "|>",
}


@dataclass(frozen=True)
class HighlightSpan:
    text: str
    color: str | None


def _string_literal(value: str) -> str:
    escaped = (
        value
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _token_end(src: str, token: t1.Token) -> int:
    if token.kind in {
        t1.Kind.TK_IDENT,
        t1.Kind.TK_TYPE,
        t1.Kind.TK_FN_TYPE,
        t1.Kind.TK_TYPE_PARAM,
        t1.Kind.TK_STRING,
    }:
        return token.location + int(token.value)

    if token.kind == t1.Kind.TK_IDENT_CALL:
        return token.location + int(token.value) + 1

    if token.kind == t1.Kind.TK_NUMBER:
        if src.startswith("true", token.location):
            return token.location + len("true")
        if src.startswith("false", token.location):
            return token.location + len("false")
        idx = token.location
        if src.startswith("0x", idx):
            idx += 2
            while idx < len(src) and (t0.is_hex(src[idx]) or src[idx] == "_"):
                idx += 1
            return idx
        if src.startswith("0b", idx):
            idx += 2
            while idx < len(src) and src[idx] in "01_":
                idx += 1
            return idx
        while idx < len(src) and (t0.is_digit(src[idx]) or src[idx] == "_"):
            idx += 1
        return idx

    if token.kind in SINGLE_CHAR_TOKEN_TEXT:
        return token.location + 1

    if token.kind in MULTI_CHAR_TOKEN_TEXT:
        return token.location + len(MULTI_CHAR_TOKEN_TEXT[token.kind])

    if token.kind in KEYWORD_TOKEN_TEXT:
        return token.location + len(KEYWORD_TOKEN_TEXT[token.kind])

    raise ValueError(f"unhandled token kind: {token.kind}")


def _token_class(token: t1.Token) -> str | None:
    if token.kind in DECLARATION_KINDS:
        return "declaration"
    if token.kind in KEYWORD_KINDS:
        return "keyword"
    if token.kind == t1.Kind.TK_IDENT_CALL:
        return "function"
    if token.kind in {t1.Kind.TK_TYPE, t1.Kind.TK_FN_TYPE, t1.Kind.TK_TYPE_PARAM}:
        return "type"
    if token.kind == t1.Kind.TK_STRING:
        return "string"
    if token.kind == t1.Kind.TK_NUMBER:
        return "number"
    if token.kind in BRACE_KINDS:
        return "brace"
    if token.kind in PUNCTUATION_KINDS:
        return "punctuation"
    if token.kind in OPERATOR_KINDS:
        return "operator"
    if token.kind == t1.Kind.TK_IDENT:
        return "identifier"
    return None


def _starts_with_name(src: str, idx: int, name: str) -> bool:
    return t0._starts_with_name(src, idx, name)


def _highlight_plain(src: str, theme: dict[str, str]) -> list[HighlightSpan]:
    spans: list[HighlightSpan] = []
    cursor = 0

    while cursor < len(src):
        comment_start = src.find("#", cursor)
        if comment_start == -1:
            spans.append(HighlightSpan(src[cursor:], None))
            break
        if cursor < comment_start:
            spans.append(HighlightSpan(src[cursor:comment_start], None))
        comment_end = t0.skip_comment(src, comment_start)
        spans.append(HighlightSpan(src[comment_start:comment_end], theme["comment"]))
        cursor = comment_end

    return spans


def _highlight_trivia(src: str, start: int, theme: dict[str, str]) -> tuple[list[HighlightSpan], int]:
    end = t0.skip_trivia(src, start)
    if start == end:
        return [], start
    return _highlight_plain(src[start:end], theme), end


def _highlight_suffix(src: str, start: int, theme: dict[str, str]) -> tuple[list[HighlightSpan], int]:
    idx = t0.skip_horizontal_whitespace(src, start)
    spans: list[HighlightSpan] = []
    if start < idx:
        spans.append(HighlightSpan(src[start:idx], None))

    if idx < len(src) and src[idx] == "#":
        comment_end = t0.skip_comment(src, idx)
        spans.append(HighlightSpan(src[idx:comment_end], theme["comment"]))
        idx = comment_end

    if idx < len(src) and src[idx] in t0.vertical_whitespace:
        line_end = idx + 1
        if src[idx] == "\r" and line_end < len(src) and src[line_end] == "\n":
            line_end += 1
        spans.append(HighlightSpan(src[idx:line_end], None))
        idx = line_end

    return spans, idx


def _highlight_string_at(src: str, start: int, theme: dict[str, str]) -> tuple[list[HighlightSpan], int]:
    end = t0.string_end(src, start)
    return [HighlightSpan(src[start:end], theme["string"])], end


def _highlight_metatag(name: str, theme: dict[str, str]) -> list[HighlightSpan]:
    return [
        HighlightSpan("$", theme["operator"]),
        HighlightSpan(name[1:], theme["meta"]),
    ]


def _highlight_import_directive(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int] | None:
    if not _starts_with_name(src, start, "import"):
        return None

    spans = [HighlightSpan("import", theme["keyword"])]
    idx = start + len("import")
    next_idx = t0.skip_horizontal_whitespace(src, idx)
    if idx < next_idx:
        spans.append(HighlightSpan(src[idx:next_idx], None))
    idx = next_idx

    if idx < len(src) and src[idx] == "p" and idx + 1 < len(src) and src[idx + 1] == '"':
        spans.append(HighlightSpan("p", theme["function"]))
        string_spans, idx = _highlight_string_at(src, idx + 1, theme)
        spans.extend(string_spans)

    suffix_spans, idx = _highlight_suffix(src, idx, theme)
    spans.extend(suffix_spans)
    return spans, idx


def _highlight_supported_targets_directive(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int] | None:
    name = "$supported_targets"
    if not _starts_with_name(src, start, name):
        return None

    spans = _highlight_metatag(name, theme)
    idx = start + len(name)

    while idx < len(src):
        next_idx = t0.skip_horizontal_whitespace(src, idx)
        if idx < next_idx:
            spans.append(HighlightSpan(src[idx:next_idx], None))
        idx = next_idx

        if idx < len(src) and src[idx] == "=":
            spans.append(HighlightSpan("=", theme["operator"]))
            idx += 1
            continue
        if idx < len(src) and src[idx] in "[]":
            spans.append(HighlightSpan(src[idx], theme["brace"]))
            idx += 1
            if src[idx - 1] == "]":
                break
            continue
        if idx < len(src) and src[idx] == '"':
            string_spans, idx = _highlight_string_at(src, idx, theme)
            spans.extend(string_spans)
            continue
        break

    suffix_spans, idx = _highlight_suffix(src, idx, theme)
    spans.extend(suffix_spans)
    return spans, idx


def _highlight_diagnostic_directive(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int] | None:
    if _starts_with_name(src, start, "$warning"):
        name = "$warning"
    elif _starts_with_name(src, start, "$error"):
        name = "$error"
    else:
        return None

    spans = _highlight_metatag(name, theme)
    idx = start + len(name)
    next_idx = t0.skip_horizontal_whitespace(src, idx)
    if idx < next_idx:
        spans.append(HighlightSpan(src[idx:next_idx], None))
    idx = next_idx

    if idx < len(src) and src[idx] == "(":
        spans.append(HighlightSpan("(", theme["punctuation"]))
        idx += 1

    next_idx = t0.skip_horizontal_whitespace(src, idx)
    if idx < next_idx:
        spans.append(HighlightSpan(src[idx:next_idx], None))
    idx = next_idx

    if idx < len(src) and src[idx] == '"':
        string_spans, idx = _highlight_string_at(src, idx, theme)
        spans.extend(string_spans)

    next_idx = t0.skip_horizontal_whitespace(src, idx)
    if idx < next_idx:
        spans.append(HighlightSpan(src[idx:next_idx], None))
    idx = next_idx

    if idx < len(src) and src[idx] == ")":
        spans.append(HighlightSpan(")", theme["punctuation"]))
        idx += 1

    suffix_spans, idx = _highlight_suffix(src, idx, theme)
    spans.extend(suffix_spans)
    return spans, idx


def _highlight_target_if_directive(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int] | None:
    if not _starts_with_name(src, start, "if"):
        return None

    spans = [HighlightSpan("if", theme["keyword"])]
    idx = start + len("if")
    trivia_spans, idx = _highlight_trivia(src, idx, theme)
    spans.extend(trivia_spans)

    if not _starts_with_name(src, idx, "$target"):
        return None
    spans.extend(_highlight_metatag("$target", theme))
    idx += len("$target")

    trivia_spans, idx = _highlight_trivia(src, idx, theme)
    spans.extend(trivia_spans)

    if src.startswith("not=?", idx):
        spans.append(HighlightSpan("not", theme["declaration"]))
        spans.append(HighlightSpan("=?", theme["operator"]))
        idx += len("not=?")
    elif src.startswith("=?", idx):
        spans.append(HighlightSpan("=?", theme["operator"]))
        idx += len("=?")
    else:
        return None

    trivia_spans, idx = _highlight_trivia(src, idx, theme)
    spans.extend(trivia_spans)

    if idx < len(src) and src[idx] == '"':
        string_spans, idx = _highlight_string_at(src, idx, theme)
        spans.extend(string_spans)

    trivia_spans, idx = _highlight_trivia(src, idx, theme)
    spans.extend(trivia_spans)

    if idx >= len(src) or src[idx] != "{":
        return None
    spans.append(HighlightSpan("{", theme["brace"]))
    idx += 1

    block_spans, idx = _highlight_prelude_block(src, idx, theme)
    spans.extend(block_spans)

    suffix_spans, idx = _highlight_suffix(src, idx, theme)
    spans.extend(suffix_spans)
    return spans, idx


def _highlight_prelude_item(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int] | None:
    for highlighter in (
        _highlight_import_directive,
        _highlight_supported_targets_directive,
        _highlight_target_if_directive,
        _highlight_diagnostic_directive,
    ):
        result = highlighter(src, start, theme)
        if result is not None:
            return result
    return None


def _highlight_prelude_block(
    src: str,
    start: int,
    theme: dict[str, str],
) -> tuple[list[HighlightSpan], int]:
    spans: list[HighlightSpan] = []
    cursor = start

    while cursor < len(src):
        trivia_spans, item_start = _highlight_trivia(src, cursor, theme)
        spans.extend(trivia_spans)
        cursor = item_start

        if cursor < len(src) and src[cursor] == "}":
            spans.append(HighlightSpan("}", theme["brace"]))
            return spans, cursor + 1

        item = _highlight_prelude_item(src, cursor, theme)
        if item is None:
            return spans, cursor

        item_spans, cursor = item
        spans.extend(item_spans)

    return spans, cursor


def _highlight_prelude(src: str, theme: dict[str, str]) -> tuple[list[HighlightSpan], int]:
    spans: list[HighlightSpan] = []
    cursor = 0

    while cursor < len(src):
        trivia_spans, item_start = _highlight_trivia(src, cursor, theme)
        spans.extend(trivia_spans)
        cursor = item_start

        item = _highlight_prelude_item(src, cursor, theme)
        if item is None:
            return spans, cursor

        item_spans, cursor = item
        spans.extend(item_spans)

    return spans, cursor


def _highlight_t1_spans(src: str, theme: dict[str, str]) -> list[HighlightSpan]:
    theme = DEFAULT_THEME if theme is None else theme
    tokens = t1.tokenize(src)
    spans: list[HighlightSpan] = []
    cursor = 0

    for token in tokens:
        start = token.location
        end = _token_end(src, token)
        span_start = start
        if token.kind == t1.Kind.TK_TYPE and start > 0 and src[start - 1] == ":":
            span_start = start - 1
        elif token.kind == t1.Kind.TK_FN_TYPE and start >= 2 and src[start - 2:start] == ":>":
            span_start = start - 2
        elif token.kind == t1.Kind.TK_NOT_EQ and start >= 3 and src[start - 3:start] == "not":
            span_start = start - 3
        if cursor < span_start:
            spans.extend(_highlight_plain(src[cursor:span_start], theme))

        token_class = _token_class(token)
        color = theme.get(token_class) if token_class is not None else None

        if token.kind == t1.Kind.TK_IDENT_CALL:
            name_end = start + int(token.value)
            spans.append(HighlightSpan(src[start:name_end], theme["function"]))
            spans.append(HighlightSpan(src[name_end:end], theme["punctuation"]))
        elif token.kind == t1.Kind.TK_TYPE and start > 0 and src[start - 1] == ":":
            spans.append(HighlightSpan(":", theme["operator"]))
            spans.append(HighlightSpan(src[start:end], theme["type"]))
        elif token.kind == t1.Kind.TK_FN_TYPE and start >= 2 and src[start - 2:start] == ":>":
            spans.append(HighlightSpan(":>", theme["operator"]))
            spans.append(HighlightSpan(src[start:end], theme["type"]))
        elif token.kind == t1.Kind.TK_NOT_EQ and start >= 3 and src[start - 3:start] == "not":
            spans.append(HighlightSpan("not", theme["declaration"]))
            spans.append(HighlightSpan(src[start:end], theme["operator"]))
        else:
            spans.append(HighlightSpan(src[start:end], color))
        cursor = end

    if cursor < len(src):
        spans.extend(_highlight_plain(src[cursor:], theme))
    return spans


def highlighted_spans(src: str, theme: dict[str, str] | None = None) -> list[HighlightSpan]:
    theme = DEFAULT_THEME if theme is None else theme
    spans, cursor = _highlight_prelude(src, theme)

    if cursor < len(src):
        spans.extend(_highlight_t1_spans(src[cursor:], theme))
    return spans


def merge_plain_spans(spans: Iterable[HighlightSpan]) -> list[HighlightSpan]:
    merged: list[HighlightSpan] = []
    for span in spans:
        if not span.text:
            continue
        if merged and merged[-1].color == span.color:
            merged[-1] = HighlightSpan(merged[-1].text + span.text, span.color)
        else:
            merged.append(span)
    return merged


def generate_highlighted_udewy_calls(
    src: str,
    parent: str = "code",
    append_text_fn: str = "Web_AppendText",
    append_token_fn: str = "append_code_token",
) -> str:
    lines: list[str] = []
    for span in merge_plain_spans(highlighted_spans(src)):
        text = _string_literal(span.text)
        if span.color is None:
            lines.append(f"    {append_text_fn}({parent} {text})")
        else:
            lines.append(f"    {append_token_fn}({parent} {text} \"{span.color}\")")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate udewy DOM calls for a highlighted udewy source block.",
    )
    parser.add_argument("source", nargs="?", help="source file to highlight; reads stdin when omitted")
    parser.add_argument("--parent", default="code", help="udewy variable name for the target DOM node")
    args = parser.parse_args()

    if args.source is None:
        src = sys.stdin.read()
    else:
        src = Path(args.source).read_text()

    print(generate_highlighted_udewy_calls(src, parent=args.parent))


if __name__ == "__main__":
    main()
