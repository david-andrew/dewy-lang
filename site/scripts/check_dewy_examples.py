"""Validate every published Dewy snippet with explicit per-example metadata."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODES = {'check', 'run', 'reject', 'design-only'}
MARKER = re.compile(r'(?:>\s*)?<!--\s*dewy-example:\s*(\{.*\})\s*-->')
FENCE = re.compile(r'^(?P<quote>>\s*)?```dewy\s*$')

@dataclass
class Example:
    page: Path
    line: int
    source: str
    metadata: dict

    @property
    def id(self):
        return self.page.relative_to(REPO_ROOT).as_posix() + ':' + str(self.line)


def published_pages() -> list[Path]:
    pages = []
    for book in ('learn', 'reference'):
        root = REPO_ROOT / 'site' / book / 'src'
        for target in re.findall(r']\(([^)#]+\.md)(?:#[^)]+)?\)', (root / 'SUMMARY.md').read_text()):
            pages.append(root / target)
    return list(dict.fromkeys(pages))


def metadata(value: str | None, location: str) -> dict:
    if value is None:
        raise ValueError(f'{location}: missing explicit dewy-example metadata')
    data = json.loads(value)
    if data.get('mode') not in MODES:
        raise ValueError(f'{location}: mode must be one of {sorted(MODES)}')
    if data['mode'] == 'run' and not isinstance(data.get('stdout'), str):
        raise ValueError(f'{location}: run requires exact stdout')
    if data['mode'] == 'reject' and not data.get('diagnostic'):
        raise ValueError(f'{location}: reject requires a diagnostic substring')
    return data


def examples_in(page: Path) -> list[Example]:
    lines = page.read_text().splitlines()
    examples = []
    i = 0
    while i < len(lines):
        opened = FENCE.match(lines[i])
        if not opened:
            i += 1
            continue
        start = i
        quote = opened['quote'] or ''
        i += 1
        body = []
        while i < len(lines) and lines[i] != f'{quote}```':
            body.append(lines[i].removeprefix(quote) if quote else lines[i])
            i += 1
        if i == len(lines):
            raise ValueError(f'{page}:{start+1}: unclosed Dewy fence')
        previous = start-1
        while previous >= 0 and not lines[previous].strip(): previous -= 1
        marker = MARKER.fullmatch(lines[previous].strip()) if previous >= 0 else None
        data = metadata(marker[1] if marker else None, f'{page}:{start+1}')
        examples.append(Example(page, start+1, '\n'.join(body)+'\n', data))
        i += 1
    return examples


class StaticExamples(HTMLParser):
    def __init__(self, page):
        super().__init__(convert_charrefs=True)
        self.page, self.examples, self.current, self.parts = page, [], None, []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'code' and 'language-dewy' in attrs.get('class', '').split():
            line = self.getpos()[0]
            self.current = (line, metadata(attrs.get('data-example'), f'{self.page}:{line}'))
            self.parts = []
    def handle_data(self, data):
        if self.current: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'code' and self.current:
            line, data = self.current
            self.examples.append(Example(self.page, line, ''.join(self.parts), data))
            self.current = None


def discover() -> list[Example]:
    examples = [e for p in published_pages() for e in examples_in(p)]
    for p in sorted((REPO_ROOT / 'site/static').rglob('*.html')):
        parser = StaticExamples(p); parser.feed(p.read_text()); examples.extend(parser.examples)
    return examples


def compiler_path(value: str | None = None) -> Path:
    if value:
        return Path(value).resolve(strict=True)
    result = subprocess.run([sys.executable, '-m', 'tools.core', 'path'], cwd=REPO_ROOT,
                            capture_output=True, text=True, check=True)
    return Path(result.stdout.strip().splitlines()[-1]).resolve(strict=True)


def validate(example: Example, compiler: Path, scratch: Path) -> dict:
    data = example.metadata
    mode = data['mode']
    result = {'id': example.id, 'mode': mode, 'target': ('native-release' if mode == 'run' else 'compiler-check' if mode != 'design-only' else None),
              'status': 'design only' if mode == 'design-only' else 'tested example'}
    if mode == 'design-only': return result
    with tempfile.TemporaryDirectory(prefix='example-', dir=scratch) as directory:
        work = Path(directory)
        for name, content in data.get('fixtures', {}).items():
            path = (work / name).resolve()
            if not path.is_relative_to(work): raise ValueError('fixture escapes example directory')
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
        source = work / 'example.dewy'
        # Blank lines keep diagnostics aligned with the documentation source.
        source.write_text('\n'*(example.line) + data.get('prefix', '') + example.source + data.get('suffix', ''))
        def call(args):
            return subprocess.run(args, cwd=work, capture_output=True, timeout=60,
                                  env={k:v for k,v in os.environ.items() if not k.startswith('SLOPPY_')})
        checked = call([compiler, 'check', source])
        diagnostic = (checked.stdout+checked.stderr).decode(errors='replace')
        if mode == 'reject':
            if checked.returncode == 0 or data['diagnostic'] not in diagnostic:
                raise ValueError(f'expected rejection containing {data["diagnostic"]!r}:\n{diagnostic}')
        else:
            if checked.returncode: raise ValueError(diagnostic)
            if mode == 'run':
                binary = work / 'example'
                built = call([compiler, 'build', source, '--release', '-o', binary])
                if built.returncode: raise ValueError((built.stdout+built.stderr).decode(errors='replace'))
                ran = call([binary, *data.get('args', [])])
                if ran.returncode != data.get('exit', 0) or ran.stdout.decode() != data['stdout']:
                    raise ValueError(f'exit {ran.returncode}, stdout {ran.stdout!r}; expected {data["stdout"]!r}')
        result['checked'] = True
        result['executed'] = mode == 'run'
    return result


def check_all(compiler: Path, scratch: Path) -> list[dict]:
    results = []
    failures = []
    for example in discover():
        try: results.append(validate(example, compiler, scratch))
        except (ValueError, subprocess.TimeoutExpired) as error:
            failures.append(f'{example.id}: {error}')
    if failures: raise ValueError('\n\n'.join(failures))
    counts = {mode: sum(r['mode'] == mode for r in results) for mode in sorted(MODES)}
    print(f'Checked {len(results)} published examples: {counts}', flush=True)
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--compiler'); cli.add_argument('--json', type=Path)
    cli.add_argument('--scratch', type=Path, default=REPO_ROOT/'site/dist/.work')
    args = cli.parse_args(); args.scratch.mkdir(parents=True, exist_ok=True)
    results = check_all(compiler_path(args.compiler), args.scratch)
    if args.json: args.json.write_text(json.dumps(results, indent=2)+'\n')

if __name__ == '__main__': main()
