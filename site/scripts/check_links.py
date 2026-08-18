"""Check that local links and assets in generated HTML resolve."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK_ATTRIBUTES = {"href", "src"}
IGNORED_SCHEMES = {"data", "http", "https", "mailto", "javascript"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in LINK_ATTRIBUTES and value:
                self.links.append(value)


def target_path(root: Path, page: Path, value: str) -> Path | None:
    parsed = urlsplit(value)
    if parsed.scheme in IGNORED_SCHEMES or parsed.netloc or not parsed.path:
        return None
    path = unquote(parsed.path)
    if path.startswith("/dewy-lang/"):
        candidate = root / path.removeprefix("/dewy-lang/")
    elif path.startswith("/"):
        return None
    else:
        candidate = page.parent / path
    if candidate.is_dir() or path.endswith("/"):
        candidate /= "index.html"
    return candidate.resolve()


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "site/dist").resolve()
    errors: list[str] = []
    for page in sorted(root.rglob("*.html")):
        parser = LinkParser()
        parser.feed(page.read_text(errors="replace"))
        for link in parser.links:
            target = target_path(root, page, link)
            if target is not None and not target.exists():
                errors.append(f"{page.relative_to(root)}: {link} -> missing {target}")
    if errors:
        print("Broken local links:", file=sys.stderr)
        print("\n".join(f"  {error}" for error in errors), file=sys.stderr)
        raise SystemExit(1)
    print(f"Checked local links in {sum(1 for _ in root.rglob('*.html'))} HTML files")


if __name__ == "__main__":
    main()
