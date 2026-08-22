"""Split ``udewy/README.md`` into an mdBook source tree."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "udewy" / "README.md"
BOOK_ROOT = REPO_ROOT / "site" / "udewy" / "reference"
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE = re.compile(r"^(`{3,}|~{3,})")
LINK = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
LOGO_BLOCK = re.compile(
    r"^<p align=\"center\">\s*<img\b[^>]*>\s*</p>\s*",
    re.IGNORECASE | re.DOTALL,
)


def github_slug(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def unique_slug(text: str, used: dict[str, int]) -> str:
    base = github_slug(text) or "section"
    count = used.get(base, 0)
    used[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def unique_filename(slug: str, used: set[str]) -> str:
    name = f"{slug}.md"
    if name == "index.md" or name in used:
        i = 1
        while True:
            candidate = f"{slug}-{i}.md"
            if candidate not in used:
                name = candidate
                break
            i += 1
    used.add(name)
    return name


@dataclass
class Block:
    level: int
    title: str
    slug: str
    lines: list[str] = field(default_factory=list)


def parse_blocks(text: str) -> list[Block]:
    used_slugs: dict[str, int] = {}
    blocks: list[Block] = [Block(0, "", "", [])]
    in_fence: str | None = None
    for line in text.splitlines():
        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)[0] * len(fence.group(1))
            if in_fence is None:
                in_fence = marker
            elif line.startswith(in_fence):
                in_fence = None
            blocks[-1].lines.append(line)
            continue
        heading = None if in_fence else HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            blocks.append(Block(level, title, unique_slug(title, used_slugs), [line]))
            continue
        blocks[-1].lines.append(line)
    return blocks


def is_part_title(title: str) -> bool:
    return bool(
        re.match(
            r"^(Part\b|Addendum\b|Backend Addendums|Misc|Files)\b",
            title,
            flags=re.IGNORECASE,
        )
    )


@dataclass
class Page:
    title: str
    filename: str
    part: str | None
    blocks: list[Block]

    def text(self) -> str:
        lines = [line for block in self.blocks for line in block.lines]
        while lines and lines[-1].strip() in {"", "---"}:
            lines.pop()
        return "\n".join(lines).strip() + "\n"

    def slugs(self) -> list[str]:
        return [block.slug for block in self.blocks if block.slug]


def split_pages(blocks: list[Block]) -> list[Page]:
    used_names = {"index.md"}
    pages: list[Page] = []
    preamble: list[Block] = []
    started = False
    current_part: str | None = None
    pending_part_blocks: list[Block] = []

    def flush_part_only(part: str, part_blocks: list[Block]) -> None:
        if not any(line.strip() for block in part_blocks for line in block.lines):
            return
        filename = unique_filename(github_slug(part) or "section", used_names)
        pages.append(Page(part, filename, part, part_blocks))

    for block in blocks:
        if not started:
            if block.level == 1 and is_part_title(block.title):
                started = True
            else:
                preamble.append(block)
                continue

        if block.level == 1:
            if pending_part_blocks and current_part is not None:
                if not any(page.part == current_part for page in pages):
                    flush_part_only(current_part, pending_part_blocks)
            current_part = block.title
            pending_part_blocks = [block]
            continue

        if block.level == 2:
            filename = unique_filename(block.slug, used_names)
            page_blocks = pending_part_blocks + [block]
            pending_part_blocks = []
            pages.append(Page(block.title, filename, current_part, page_blocks))
            continue

        if pages and pages[-1].part == current_part:
            pages[-1].blocks.append(block)
        else:
            pending_part_blocks.append(block)

    if pending_part_blocks and current_part is not None:
        if not any(page.part == current_part for page in pages):
            flush_part_only(current_part, pending_part_blocks)

    intro = [block for block in preamble if any(line.strip() for line in block.lines)]
    pages.insert(0, Page("Introduction", "index.md", None, intro))
    return pages


def rewrite_links(pages: list[Page]) -> None:
    slug_to_file: dict[str, str] = {}
    for page in pages:
        for slug in page.slugs():
            slug_to_file.setdefault(slug, page.filename)

    def replace(match: re.Match[str], filename: str) -> str:
        text, slug = match.group(1), match.group(2)
        target = slug_to_file.get(slug)
        if target is None or target == filename:
            return match.group(0)
        return f"[{text}]({target}#{slug})"

    for page in pages:
        for block in page.blocks:
            block.lines = [
                LINK.sub(lambda match: replace(match, page.filename), line)
                for line in block.lines
            ]


def summary_markdown(pages: list[Page]) -> str:
    lines = ["# µDewy Language Specification", "", "[Introduction](index.md)", ""]
    current_part: str | None = None
    for page in pages[1:]:
        if page.part != current_part:
            current_part = page.part
            if current_part:
                lines.append(f"# {current_part}")
                lines.append("")
        lines.append(f"- [{page.title}]({page.filename})")
    lines.append("")
    return "\n".join(lines)


def generate(destination: Path | None = None) -> Path:
    dest = Path(destination) if destination is not None else BOOK_ROOT / "src"
    raw = README.read_text()
    raw = LOGO_BLOCK.sub("", raw, count=1)
    pages = split_pages(parse_blocks(raw))
    rewrite_links(pages)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for page in pages:
        (dest / page.filename).write_text(page.text())
    (dest / "SUMMARY.md").write_text(summary_markdown(pages))
    return dest


def main() -> None:
    dest = generate()
    print(f"Wrote µDewy spec book source to {dest}")


if __name__ == "__main__":
    main()
