"""Verify local assets, fragments, redirect targets and redirect cycles."""
from __future__ import annotations
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.ids = set(); self.redirect = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('id', 'name'):
            if attrs.get(key): self.ids.add(attrs[key])
        for key in ('href', 'src', 'data-redirect'):
            if attrs.get(key): self.links.append(attrs[key])
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            match = re.search(r'url\s*=\s*[\'"]?([^\'"]+)', attrs.get('content', ''), re.I)
            if match: self.redirect = match[1].strip(); self.links.append(self.redirect)


def target_path(root: Path, page: Path, value: str) -> Path | None:
    url = urlsplit(value)
    if url.scheme or url.netloc:
        if url.netloc != 'dewy-lang.org': return None
    path = unquote(url.path)
    if not path: return page
    candidate = root / path.lstrip('/') if path.startswith('/') else page.parent / path
    if candidate.is_dir() or path.endswith('/'): candidate /= 'index.html'
    return candidate.resolve()


def check(root: Path) -> list[str]:
    root = root.resolve(); errors = []; pages = {}
    for page in sorted(root.rglob('*.html')):
        parser = LinkParser(); parser.feed(page.read_text(errors='replace')); pages[page] = parser
    for page, parser in pages.items():
        for link in parser.links:
            target = target_path(root, page, link)
            if target is None: continue
            message = f'{page.relative_to(root)}: {link}'
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f'{message} -> missing local target'); continue
            fragment = unquote(urlsplit(link).fragment)
            if fragment and target in pages and fragment not in pages[target].ids:
                errors.append(f'{message} -> missing fragment')
        seen = {page}; target = page
        while target in pages and pages[target].redirect:
            target = target_path(root, target, pages[target].redirect)
            if target in seen:
                errors.append(f'{page.relative_to(root)}: redirect cycle'); break
            seen.add(target)
        # Redirect stubs forward any incoming hash. Check every preserved local
        # fragment against the final destination as well as the stub itself.
        if parser.redirect:
            for fragment in parser.ids:
                target = target_path(root, page, parser.redirect)
                seen = {page}
                while target in pages and pages[target].redirect and target not in seen:
                    seen.add(target)
                    target = target_path(root, target, pages[target].redirect)
                if target in pages and target not in seen and fragment not in pages[target].ids:
                    errors.append(f'{page.relative_to(root)}: forwarded #{fragment} -> missing destination fragment')
    return errors


def main():
    root = Path(sys.argv[1] if len(sys.argv)>1 else 'site/dist').resolve()
    errors = check(root)
    if errors: raise SystemExit('Broken local links:\n'+'\n'.join(errors))
    print(f'Checked links, fragments and redirects in {len(list(root.rglob("*.html")))} HTML files')
if __name__ == '__main__': main()
