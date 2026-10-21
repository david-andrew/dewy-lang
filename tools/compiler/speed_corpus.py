"""The compile-speed corpora: which programs `speed --corpus` compiles, and how their lines are counted."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LADDER = ROOT / 'tests' / 'ladder'
TIER4_FIRST = 95        # tier 3 is programs 64-94; tier 4 programs are numbered from 95
LOCAL_IMPORT = re.compile(r'\bp"(?!@)([^"]+\.dewy)"')


def source_lines(text: str) -> int:
    """Non-blank, non-comment lines: `#` to the end of the line, nesting `#{ ... }#` blocks.
    Strings are not tracked, so a `#` or `#{` inside a string literal is read as a comment."""
    count, depth = 0, 0
    for line in text.splitlines():
        code, i = False, 0
        while i < len(line):
            pair = line[i:i + 2]
            if pair == '#{':
                depth += 1
                i += 2
            elif depth and pair == '}#':
                depth -= 1
                i += 2
            elif depth:
                i += 1
            elif line[i] == '#':
                break
            else:
                code = code or not line[i].isspace()
                i += 1
        count += code
    return count


def physical_lines(text: str) -> int:
    """Lines as the compiler's own `--time` source count has them (comments and blanks included)."""
    return len(text.splitlines())


def local_imports(path: Path) -> list[Path]:
    """The files `path` imports by relative path (`from p"model.dewy" import ...`); library imports are not these."""
    found = []
    for line in path.read_text().splitlines():
        if line.lstrip().startswith('#'):
            continue
        found.extend((path.parent / name).resolve() for name in LOCAL_IMPORT.findall(line))
    return found


def root_files(entry: Path) -> list[Path]:
    """The entry and every file it imports by relative path, in discovery order."""
    seen: list[Path] = []
    pending = [entry.resolve()]
    while pending:
        path = pending.pop(0)
        if path in seen or not path.is_file():
            continue
        seen.append(path)
        pending.extend(local_imports(path))
    return seen


def standalone(files: list[Path]) -> list[Path]:
    """The files no other file in the set imports: the programs, not their modules."""
    imported = {target for path in files for target in local_imports(path)}
    return [path for path in files if path.resolve() not in imported]


def ladder_programs(tier4: bool) -> list[Path]:
    """core.dewy of each ladder program (those that have one), tier 4 or the earlier tiers."""
    found = []
    for directory in sorted(LADDER.iterdir()):
        if directory.is_dir() and directory.name[:2].isdigit() and (directory / 'core.dewy').is_file():
            if (int(directory.name.split('_')[0]) >= TIER4_FIRST) == tier4:
                found.append(directory / 'core.dewy')
    return found


def corpora(scratch: Path) -> dict[str, list[Path]]:
    """Corpus name -> the programs compiled one by one and summed. `scratch` holds bench/game.dewy as the bench
    command builds it (its raw-syscall harness swapped for bench/harness.jo)."""
    from tools.compiler import bench

    scratch.mkdir(parents=True, exist_ok=True)
    examples = standalone(sorted((ROOT / 'examples').glob('*.dewy')))
    return {
        'compiler': standalone(sorted((ROOT / 'compiler').glob('*.dewy'))),
        'ladder+examples': ladder_programs(False) + examples,
        'game': [ROOT / 'examples/dunes.dewy', bench.prepare_source('game', scratch)],
        'tier-4': ladder_programs(True),
    }


def root_counts(entry: Path) -> tuple[int, int]:
    """(source lines, physical lines) of an entry and the local files it imports."""
    texts = [path.read_text() for path in root_files(entry)]
    return sum(map(source_lines, texts)), sum(map(physical_lines, texts))


def library_lines(time_stderr: str, root_physical: int) -> int:
    """Lines of library the compile loaded, from `build --time`'s sources line: its implementation (.jo)
    lines plus its Dewy lines beyond the root files' (physical lines: comments and unused bodies included)."""
    found = re.search(r'(\d+) Dewy lines .*?(\d+) implementation lines', time_stderr)
    if not found:
        raise ValueError('Missing sources line in --time output')
    return int(found.group(2)) + max(0, int(found.group(1)) - root_physical)
