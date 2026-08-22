"""Prerender µDewy code blocks with the tokenizer highlighter."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "udewy" / "third_party" / "web"))
sys.path.insert(0, str(REPO_ROOT))

from generate_highlighted_udewy import (  # noqa: E402
    DEFAULT_THEME,
    _highlight_plain,
    highlighted_spans,
    merge_plain_spans,
)

CLASS_THEME = {name: name for name in DEFAULT_THEME}
CODE_BLOCK = re.compile(
    r"(<code\b[^>]*\blanguage-udewy\b[^>]*>)(.*?)(</code>)",
    re.DOTALL | re.IGNORECASE,
)


def _span_html(text: str, kind: str | None) -> str:
    escaped = html.escape(text, quote=False)
    if kind is None:
        return escaped
    return f'<span class="u-{kind}">{escaped}</span>'


def highlight_source(src: str, *, lined: bool = False) -> str:
    try:
        spans = merge_plain_spans(highlighted_spans(src, CLASS_THEME))
    except (SyntaxError, ValueError):
        spans = merge_plain_spans(_highlight_plain(src, CLASS_THEME))

    lines: list[list[str]] = [[]]
    for span in spans:
        parts = span.text.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append([])
            if part:
                lines[-1].append(_span_html(part, span.color))

    if not lined:
        return "\n".join("".join(parts) for parts in lines)

    rendered: list[str] = []
    for i, parts in enumerate(lines, 1):
        rendered.append(f'<span class="ln">{i}</span>{"".join(parts)}')
    return "\n".join(rendered)


def _decorate_open_tag(tag: str) -> str:
    extras = [name for name in ("nohighlight", "udewy-hl") if name not in tag]
    if not extras:
        return tag
    classes = " ".join(extras) + " "
    if "class=" in tag:
        return re.sub(r'class="', f'class="{classes}', tag, count=1)
    return tag.replace("<code", f'<code class="{classes.strip()}"', 1)


def highlight_html(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag, inner, close_tag = match.groups()
        if "udewy-hl" in open_tag:
            return match.group(0)
        src = html.unescape(inner)
        if src.startswith("\n"):
            src = src[1:]
        if src.endswith("\n"):
            src = src[:-1]
        lined = bool(re.search(r"\blined\b", open_tag))
        return f"{_decorate_open_tag(open_tag)}{highlight_source(src, lined=lined)}{close_tag}"

    return CODE_BLOCK.sub(replace, text)


def highlight_tree(root: Path) -> None:
    root = Path(root)
    for path in root.rglob("*.html"):
        if "demos" in path.parts:
            continue
        original = path.read_text()
        updated = highlight_html(original)
        if updated != original:
            path.write_text(updated)
