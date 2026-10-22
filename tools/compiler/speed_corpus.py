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


def flagships() -> list[Path]:
    """The tier-4 flagship programs: each one's core.dewy where it has one (today's dialect), else its design.dewy."""
    found = []
    for directory in sorted(LADDER.iterdir(), key=lambda d: (d.name.split('_')[0].zfill(4), d.name)):
        if directory.is_dir() and directory.name[:2].isdigit() and int(directory.name.split('_')[0]) >= TIER4_FIRST:
            for name in ('core.dewy', 'design.dewy'):
                if (directory / name).is_file():
                    found.append(directory / name)
                    break
    return found


def median_ladder_program() -> Path:
    """The tier 1-3 ladder program (core.dewy) of median root source lines: the small-program latency probe."""
    ranked = sorted(ladder_programs(False), key=lambda path: (root_counts(path)[0], str(path)))
    return ranked[(len(ranked) - 1) // 2]


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
        'tier-4': flagships(),
    }


def root_counts(entry: Path) -> tuple[int, int]:
    """(source lines, physical lines) of an entry and the local files it imports."""
    texts = [path.read_text() for path in root_files(entry)]
    return sum(map(source_lines, texts)), sum(map(physical_lines, texts))


LINES = re.compile(r'^lines: root (\d+), library (\d+), instance (\d+); (\d+) instances', re.MULTILINE)
NODES = re.compile(r'^nodes: root (\d+), library (\d+), shared (\d+)', re.MULTILINE)


def node_total(time_stderr: str) -> int | None:
    """Every syntax node the compile made (root, library and shared), or None."""
    found = NODES.search(time_stderr)
    return sum(map(int, found.groups())) if found else None


def processed(time_stderr: str) -> dict[str, int] | None:
    """What `build --time` says the compile processed, or None (a compiler without the counts):
    root (the program's own code lines), library (the code lines of the library files it parsed, less the
    lazy bodies nobody asked for), instance (the code lines of each generic instance's declaration, once per
    instance), instances, and nodes (every syntax node made: root, library and shared). Total throughput
    counts all three line kinds; the fan-out is library + instance."""
    lines, nodes = LINES.search(time_stderr), node_total(time_stderr)
    if not lines or nodes is None:
        return None
    root, library, instance, instances = map(int, lines.groups())
    return {'root': root, 'library': library, 'instance': instance, 'instances': instances,
            'all': root + library + instance, 'nodes': nodes}


INSTRUCTION_SPLIT = re.compile(r'^instructions: (\d+)((?:; \w+ \d+:[^;\n]*)*)$', re.MULTILINE)


def instruction_split(time_stderr: str) -> dict[str, dict[str, int]] | None:
    """`build --time`'s instruction split, {side: {phase: instructions}} with each side's 'total', or None
    (a compiler without it, or no hardware counters)."""
    found = INSTRUCTION_SPLIT.search(time_stderr)
    if not found:
        return None
    split = {}
    for part in found.group(2).split('; ')[1:]:
        head, _, rest = part.partition(':')
        side, total = head.split()
        words = rest.split()
        split[side] = {'total': int(total), **{words[i]: int(words[i + 1]) for i in range(0, len(words), 2)}}
    return split
