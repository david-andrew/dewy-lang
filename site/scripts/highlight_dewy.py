"""Prerender Dewy code blocks with the extension's TextMate grammar."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = REPO_ROOT / "site"
GRAMMAR = REPO_ROOT / "dewy" / "vscode-dewy" / "syntaxes" / "dewy.tmLanguage.json"
RENDERER = SITE_ROOT / "scripts" / "render_dewy.mjs"
SHIKI_PACKAGE = SITE_ROOT / "node_modules" / "shiki" / "package.json"
CODE_BLOCK = re.compile(
    r"(<code\b[^>]*\blanguage-dewy\b[^>]*>)(.*?)(</code>)",
    re.DOTALL | re.IGNORECASE,
)
LINE_OPEN = re.compile(r'<span class="line">')
LINE_NUMBER = re.compile(r'<span class="ln">.*?</span>')
PRESENTATION_TAG = re.compile(r'</?(?:b|span)\b[^>]*>')


@dataclass(frozen=True)
class Highlighted:
    inner: str
    style: str


def _source(inner: str) -> str:
    # Static showcase snippets predate build-time highlighting and contain
    # presentation-only spans. Remove those without interpreting escaped Dewy
    # text as HTML, then feed the original source to the grammar.
    inner = LINE_NUMBER.sub("", inner)
    inner = PRESENTATION_TAG.sub("", inner)
    source = html.unescape(inner)
    return source.removeprefix("\n").removesuffix("\n")


def _with_line_numbers(inner: str) -> str:
    line = 0

    def replace(_: re.Match[str]) -> str:
        nonlocal line
        line += 1
        return f'<span class="line"><span class="ln">{line}</span>'

    return LINE_OPEN.sub(replace, inner)


def _decorate_open_tag(tag: str, style: str) -> str:
    # mdBook's highlight.js 10 checks language-* before it checks nohighlight,
    # so leaving language-dewy in place produces an unnecessary console warning.
    tag = re.sub(r"(?<=[\" ])language-dewy(?=[\" ])", "dewy-source", tag)
    extras = [name for name in ("nohighlight", "dewy-hl") if name not in tag]
    if extras:
        classes = " ".join(extras) + " "
        if "class=" in tag:
            tag = re.sub(r'class="', f'class="{classes}', tag, count=1)
        else:
            tag = tag.replace("<code", f'<code class="{classes.strip()}"', 1)
    if style and "style=" not in tag:
        tag = tag.replace(">", f' style="{html.escape(style, quote=True)}">', 1)
    return tag


def _render_sources(sources: list[str], node: str) -> dict[str, Highlighted]:
    if not sources:
        return {}
    if not SHIKI_PACKAGE.is_file():
        raise SystemExit(
            "Required site dependencies are missing. Run `npm ci --prefix site`."
        )
    completed = subprocess.run(
        [node, str(RENDERER), str(GRAMMAR)],
        input=json.dumps(sources),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise SystemExit(completed.stderr.strip() or "Dewy highlighting failed")
    try:
        rendered = json.loads(completed.stdout)
        if len(rendered) != len(sources):
            raise ValueError("renderer returned the wrong number of results")
        return {
            source: Highlighted(result["inner"], result["style"])
            for source, result in zip(sources, rendered, strict=True)
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Invalid response from Dewy highlighter: {error}") from error


def highlight_html(text: str, highlighted: dict[str, Highlighted]) -> str:
    def replace(match: re.Match[str]) -> str:
        open_tag, inner, close_tag = match.groups()
        if "dewy-hl" in open_tag:
            return match.group(0)
        rendered = highlighted[_source(inner)]
        highlighted_inner = (
            _with_line_numbers(rendered.inner)
            if re.search(r"\blined\b", open_tag)
            else rendered.inner
        )
        return (
            f"{_decorate_open_tag(open_tag, rendered.style)}"
            f"{highlighted_inner}{close_tag}"
        )

    return CODE_BLOCK.sub(replace, text)


def highlight_tree(root: Path, *, node: str | None = None) -> int:
    root = Path(root)
    paths = sorted(root.rglob("*.html"))
    originals = {path: path.read_text() for path in paths}
    sources = sorted(
        {
            _source(match.group(2))
            for text in originals.values()
            for match in CODE_BLOCK.finditer(text)
            if "dewy-hl" not in match.group(1)
        }
    )
    if not sources:
        return 0
    node = node or shutil.which("node")
    if node is None:
        raise SystemExit(
            "Required tool 'node' was not found on PATH. See site/README.md for setup."
        )
    highlighted = _render_sources(sources, node)
    count = 0
    for path, original in originals.items():
        updated = highlight_html(original, highlighted)
        if updated != original:
            count += len(CODE_BLOCK.findall(original))
            path.write_text(updated)
    print(f"Prerendered {count} Dewy code blocks from {GRAMMAR.relative_to(REPO_ROOT)}")
    return count
