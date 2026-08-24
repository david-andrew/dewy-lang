"""Validate Dewy examples in the published Learn and Reference books."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dewy.parser import p0, t1
from dewy.reporting import SrcFile
from dewy.semantic import check


SUMMARIES = (
    REPO_ROOT / "site" / "learn" / "src" / "SUMMARY.md",
    REPO_ROOT / "site" / "reference" / "src" / "SUMMARY.md",
)
PAGE_LINK = re.compile(r"]\(([^)#]+\.md)(?:#[^)]+)?\)")
MARKER = re.compile(
    r"(?:>\s*)?<!--\s*dewy-example:\s*(parser|compiler|design-only)\s*-->"
)
OPEN_FENCE = re.compile(r"^(?P<quote>>\s*)?```dewy\s*$")


@dataclass(frozen=True)
class Example:
    page: Path
    line: int
    source: str
    mode: str


def published_pages() -> list[Path]:
    pages: list[Path] = []
    for summary in SUMMARIES:
        for target in PAGE_LINK.findall(summary.read_text()):
            page = (summary.parent / target).resolve()
            if page not in pages:
                pages.append(page)
    return pages


def examples_in(page: Path) -> list[Example]:
    lines = page.read_text().splitlines()
    examples: list[Example] = []
    index = 0
    while index < len(lines):
        opened = OPEN_FENCE.match(lines[index])
        if opened is None:
            index += 1
            continue

        quote = opened.group("quote") or ""
        start = index
        index += 1
        body: list[str] = []
        closing = f"{quote}```"
        while index < len(lines) and lines[index] != closing:
            line = lines[index]
            if quote and line.startswith(quote):
                line = line[len(quote):]
            body.append(line)
            index += 1
        if index == len(lines):
            raise ValueError(f"{page}:{start + 1}: unclosed Dewy code fence")

        previous = start - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        marker = MARKER.fullmatch(lines[previous].strip()) if previous >= 0 else None
        mode = marker.group(1) if marker else "parser"
        examples.append(Example(page, start + 1, "\n".join(body), mode))
        index += 1
    return examples


def validate(example: Example) -> None:
    if example.mode == "design-only":
        return

    source = SrcFile(None, example.source)
    # A comments-only example is lexically valid but has no root AST.
    tokens = t1.tokenize(source)
    if not tokens or all(isinstance(token, t1.Whitespace) for token in tokens):
        return
    if example.mode == "compiler":
        check.typecheck_and_resolve(source)
    else:
        p0.parse(source)


def main() -> None:
    examples = [example for page in published_pages() for example in examples_in(page)]
    counts = {mode: 0 for mode in ("compiler", "parser", "design-only")}
    failures: list[str] = []
    for example in examples:
        counts[example.mode] += 1
        try:
            validate(example)
        except BaseException as error:
            detail = str(error).strip() or repr(error)
            failures.append(
                f"{example.page.relative_to(REPO_ROOT)}:{example.line} "
                f"({example.mode}): {detail}"
            )

    if failures:
        print("Invalid published Dewy examples:", file=sys.stderr)
        print("\n\n".join(failures), file=sys.stderr)
        raise SystemExit(1)

    print(
        f"Checked {len(examples)} published Dewy examples "
        f"({counts['compiler']} compiler, {counts['parser']} parser, "
        f"{counts['design-only']} design-only)"
    )


if __name__ == "__main__":
    main()
