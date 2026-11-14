"""Fixed-capability source control: one compiler builds current leaves and their Jo twins.

No second compiler is built. Four whole-program samples include the library closure
and shared passes. Both forms use the same staging path, executable and library.
The default covers current implementation leaves. Bootstrap stubs and the shared
layouts their Dewy implementations require stay unmodified on both sides;
explicit selectors can narrow the control to a series.

All comparable current leaves::

    python3 -m tools.core speed --equivalent-only

Hot-series control (new leaves plus the three expanded existing leaves)::

    python3 -m tools.core speed --equivalent-only --equivalent-since 31fcff250 \
        --equivalent-leaves inline_ops,prelude_ops,dewy_node_ops

Use --equivalent to include the all-leaf control in the normal speed gate.
Explicit selectors also include their control without --equivalent-only. This
companion metric does not waive the cumulative raw self-build source-cost cap.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from tools.compiler.twin_guard import BOOTSTRAP_STUBS

# call_forward has no real Jo implementation. Its remaining Dewy code needs
# NK, SK and TK as literal unions, so keep their layout owners on both sides.
# Switching these owners to Jo enums would make the control unbuildable.
FIXED_LAYOUTS = {'node_store', 'checker_state', 'checker_types'}


@dataclass(frozen=True)
class Equivalent:
    leaves: tuple[str, ...]
    dewy: int
    jo: int

    @property
    def ratio(self) -> float:
        return self.dewy / self.jo

    @property
    def meets_target(self) -> bool:
        return self.dewy <= self.jo


def selected(root: Path, since: str | None, extra: list[str], git) -> tuple[str, ...]:
    names = {name.strip() for part in extra for name in part.split(',') if name.strip()}
    if since:
        # Compare the base inventory with the working tree, including a new, uncommitted round.
        previous = set(git('ls-tree', '-r', '--name-only', since, 'compiler').splitlines())
        names.update(p.stem for p in (root / 'compiler').glob('*.dewy')
                     if f'compiler/{p.name}' not in previous)
    if since is None and not extra:
        names = {p.stem for p in (root / 'compiler').glob('*.dewy')} - BOOTSTRAP_STUBS.keys() - FIXED_LAYOUTS
    if not names:
        raise ValueError('no equivalent compiler leaves selected')
    for name in sorted(names):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
            raise ValueError(f'invalid compiler leaf: {name}')
        if name in BOOTSTRAP_STUBS:
            raise ValueError(f'{name} has a bootstrap stub, not an equivalent Jo twin')
        for suffix in ('.dewy', '.jo'):
            if not (root / 'compiler' / (name + suffix)).is_file():
                raise ValueError(f'missing equivalent source: compiler/{name}{suffix}')
    return tuple(sorted(names))


def freeze(compiler: Path, leaves: tuple[str, ...]) -> None:
    """Redirect import declarations only, including callers in other Dewy leaves.

    Keep the same module paths on both sides except the selected suffixes. Never
    replace a diagnostic, comment, or program string that mentions a leaf.
    """
    names = '|'.join(re.escape(n) for n in leaves)
    # Consume complete strings/comments before looking for another declaration.
    # A template containing a line that looks like an import is source data.
    quoted = (r'"""[\s\S]*?"""' r"|'''[\s\S]*?'''"
              r'|"(?:\\[\s\S]|[^"\\])*"' r"|'(?:\\[\s\S]|[^'\\])*'")
    declaration = (r"(?P<edge>^[ \t]*(?:use[ \t]+|(?:from|import)[ \t]+p?)"
                   r"(?P<quote>['\"])(?:\./)?(?:" + names + r")\.dewy(?P=quote))")
    tokens = re.compile(declaration + r"|\#[^\n]*|" + quoted, re.MULTILINE)
    def replace(match):
        text = match.group()
        return text[:-5] + 'jo' + text[-1] if match.group('edge') else text
    for path in compiler.iterdir():
        if path.suffix in ('.jo', '.dewy'):
            text = path.read_text()
            changed = tokens.sub(replace, text)
            if changed != text:
                path.write_text(changed)


def measure(root: Path, staging: Path, leaves: tuple[str, ...], count) -> Equivalent:
    """count must measure the entire build and reject unstable/failed samples."""
    compiler = staging / 'compiler'
    shutil.rmtree(compiler, ignore_errors=True)
    shutil.copytree(root / 'compiler', compiler)
    source = str(compiler / 'main.jo')
    dewy = count(source)
    freeze(compiler, leaves)
    jo = count(source)
    if dewy <= 0 or jo <= 0:
        raise ValueError('equivalent-source instruction counts must be positive')
    return Equivalent(leaves, dewy, jo)


def report(result: Equivalent) -> None:
    print(f'  equivalent source ({len(result.leaves)} leaves): Dewy {result.dewy} / Jo {result.jo}'
          f' = {result.ratio:.17g}x (target <=1.00x; '
          f'{"met" if result.meets_target else "not met"})', flush=True)
    print('    leaves: ' + ', '.join(result.leaves), flush=True)
    print('    fixed support: ' + ', '.join(sorted(BOOTSTRAP_STUBS.keys() | FIXED_LAYOUTS))
          + ' (Dewy on both sides: bootstrap stub and its literal-union layouts)', flush=True)
