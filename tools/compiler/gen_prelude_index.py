"""Generate or check the optional prelude index in compiler/prelude.jo.

Run python3 tools/compiler/gen_prelude_index.py after changing a library.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import reduce
from itertools import pairwise
from operator import and_, or_
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START = '# BEGIN GENERATED PRELUDE INDEX'
END = '# END GENERATED PRELUDE INDEX'
IDENT = r'[A-Za-z_\x80-\U0010ffff][A-Za-z_0-9\x80-\U0010ffff]*'
TOKEN = re.compile(rf'#[^\n]*|[\t \r]+|\n|[\x27"]|{IDENT}|[^\W_]+|==|=>|[^\s]')
NAME = re.compile(IDENT)
ATTRIBUTE = re.compile(rf'@{IDENT}')
JO_DECL = re.compile(
    rf'(?:const|extern|struct|enum|type)\s+({IDENT})'
    rf'|(?:let\s+)?((?:{IDENT}\s*,\s*)*{IDENT}|\([^\s()]+\))'
    rf'(?:\s*\[[^\n]*?\])?\s*(?:=(?!=|>)|:)'
)
DEWY_DECL = re.compile(rf'(?:(?:let|const)\s+)?({IDENT})\s*(?:=(?!=|>)|:)')
WHEN = re.compile(r'(?:else\s+(?:when|if)\b|when\b|else\s*(?=:))')
TARGET_BITS = {name: 1 << i for i, name in enumerate(('linux', 'windows', 'macos', 'wasm'))}
ALL_TARGETS = sum(TARGET_BITS.values())
TARGET_LITERALS = {f'"{name}"' for name in TARGET_BITS}
TARGET_TEST = re.compile(r'TARGET\s*(==|!=)\s*"([a-z]+)"')
# These modules supply runtime hooks while the rest of the game library is deferred.
LAZY_GAME_MODULES = {'dl.jo', 'gpuarray.jo', 'metal.jo', 'vk.jo'}


def raw_string(source: str, start: int) -> bool:
    return start > 0 and source[start - 1] == 'r' and (
        start == 1 or not re.fullmatch(r'[A-Za-z_0-9\x80-\U0010ffff]', source[start - 2])
    )


def string_end(source: str, start: int, raw: bool, references: set[str]) -> int:
    quote = '"""' if source.startswith('"""', start) else source[start]
    i = start + len(quote)
    while i < len(source):
        if source.startswith(quote, i):
            return i + len(quote)
        if not raw and source[i] == '\\':
            i += 2
            continue
        if not raw and source[i] == '{':
            if source.startswith('{{', i):
                i += 2
                continue
            # A brace alone is also accepted as a one-character string.
            following = source[i + 2:i + 3]
            if (i == start + 1 and source.startswith(quote, i + 1)
                    and not following.isalnum() and following not in ('_', '"', "'")):
                i += 1
                continue
            depth = 1
            i += 1
            while depth:
                token = TOKEN.match(source, i)
                if not token:
                    raise ValueError('unterminated interpolation')
                word = token[0]
                end = token.end()
                if word in ('"', "'"):
                    end = string_end(source, i, raw_string(source, i), references)
                elif word == '{':
                    depth += 1
                elif word == '}':
                    depth -= 1
                elif NAME.fullmatch(word):
                    references.add(word)
                i = end
            continue
        i += 1
    raise ValueError('unterminated string')


def lexical_source(source: str, dewy: bool) -> tuple[str, set[str]]:
    """Blank comments and mask literal text, keeping line and token positions."""
    code = []
    references: set[str] = set()
    i = 0
    while i < len(source):
        token = TOKEN.match(source, i)
        if not token:
            code.append(source[i])
            i += 1
            continue
        word = token[0]
        end = token.end()
        if word in ('"', "'"):
            end = string_end(source, i, raw_string(source, i), references)
            literal = source[i:end]
            code.append(literal if literal in TARGET_LITERALS else re.sub(r'[^\n]', '~', literal))
        elif word.startswith('#'):
            if dewy and word.startswith('#{'):
                depth = 0
                for delimiter in re.finditer(r'#\{|\}#', source[i:]):
                    depth += 1 if delimiter[0] == '#{' else -1
                    if depth == 0:
                        end = i + delimiter.end()
                        break
                else:
                    raise ValueError('unterminated block comment')
            code.append(re.sub(r'[^\n]', ' ', source[i:end]))
        else:
            code.append(word)
            if NAME.fullmatch(word):
                references.add(word)
        i = end
    return ''.join(code), references


def logical_lines(code: str):
    """Fold bracketed continuations while keeping the leading indentation."""
    parts = []
    indent = 0
    depth = 0
    for line in code.splitlines():
        head = line.lstrip()
        if not head:
            continue
        if not parts:
            if head.startswith('~'):
                continue
            indent = len(line[:len(line) - len(head)].expandtabs())
        parts.append(head)
        depth += sum(head.count(c) for c in '([{') - sum(head.count(c) for c in ')]}')
        if depth == 0:
            yield indent, ' '.join(parts)
            parts.clear()


def target_mask(condition: str) -> int | None:
    """Evaluate the TARGET-only comparisons recognized by the Jo scanner."""
    if not condition:
        return ALL_TARGETS
    parts = re.split(r'\s+(and|or)\s+', condition)
    joiners = set(parts[1::2])
    if len(joiners) > 1:
        return None
    masks = []
    for part in parts[::2]:
        match = TARGET_TEST.fullmatch(part)
        if match is None or match[2] not in TARGET_BITS:
            return None
        bit = TARGET_BITS[match[2]]
        masks.append(bit if match[1] == '==' else ALL_TARGETS ^ bit)
    return reduce(or_ if 'or' in joiners else and_, masks)


def declarations(code: str, suffix: str) -> dict[str, int]:
    """Read declarations and their possible targets, including every 'when' arm."""
    names: dict[str, int] = defaultdict(int)
    # Each entry holds the header indentation, body indentation, and active targets.
    branches: list[tuple[int, int, int]] = []
    pending: tuple[int, int] | None = None
    remaining: dict[int, int] = {}
    pattern = JO_DECL if suffix == '.jo' else DEWY_DECL
    for indent, head in logical_lines(code):
        while branches and indent <= branches[-1][0]:
            branches.pop()
        if pending is not None:
            parent, mask = pending
            if indent > parent:
                branches.append((parent, indent, mask))
            pending = None
        if indent != (branches[-1][1] if branches else 0):
            continue
        active = branches[-1][2] if branches else ALL_TARGETS
        while attribute := ATTRIBUTE.match(head):
            head = head[attribute.end():].lstrip()
            if head.startswith('('):
                level = 0
                for i, char in enumerate(head):
                    level += (char == '(') - (char == ')')
                    if level == 0:
                        head = head[i + 1:].lstrip()
                        break
        while branch := WHEN.match(head):
            # The Jo parser accepts a declaration on the same line as a branch header.
            level = 0
            for i, char in enumerate(head):
                if char == ':' and level == 0:
                    if head.startswith('else'):
                        active &= remaining.get(indent, ALL_TARGETS)
                    mask = target_mask(head[branch.end():i].strip())
                    # Either arm of a condition involving other constants may apply.
                    remaining[indent] = active if mask is None else active & ~mask
                    if mask is not None:
                        active &= mask
                    head = head[i + 1:].lstrip()
                    if not head:
                        pending = (indent, active)
                    break
                level += (char in '([{') - (char in ')]}')
            else:
                head = ''
        match = pattern.match(head)
        if match:
            declared = next(group for group in match.groups() if group is not None)
            entries = [declared[1:-1]] if declared.startswith('(') else map(str.strip, declared.split(','))
            for name in entries:
                if name != '_':
                    names[name] |= active
    return names


@dataclass
class Library:
    files: dict[Path, set[str]]
    references: dict[Path, set[str]]
    optional: dict[str, dict[str, set[str]]]
    game_targets: dict[str, dict[str, int]]


def read_library(root: Path, prelude: str) -> Library:
    policy = re.search(r'^std_optional_file = .*\n\s*n in \[([^\]]*)\]', prelude, re.MULTILINE)
    if policy is None:
        raise ValueError('cannot read std_optional_file in compiler/prelude.jo')
    std_files = set(re.findall(r'"([^"]+)"', policy[1]))
    files = {}
    references = {}
    optional: dict[str, dict[str, set[str]]] = {'std': {}, 'game': {}}
    game_targets = {}
    for folder in ('core', 'runtime', 'std', 'prelude', 'game'):
        directory = root / 'lib' / folder
        for path in sorted(directory.rglob('*')):
            if path.suffix not in ('.jo', '.dewy') or not path.is_file():
                continue
            relative = path.relative_to(root)
            try:
                code, words = lexical_source(path.read_text(encoding='utf-8'), dewy=path.suffix == '.dewy')
            except ValueError as error:
                raise ValueError(f'{relative}: {error}') from error
            declared = declarations(code, path.suffix)
            names = set(declared)
            files[relative] = names
            if folder != 'game':
                references[relative] = words
            # checker_startup implicitly loads top-level .jo files. Dewy
            # prelude modules have a separate index, and signals.dewy is imported.
            if path.parent != directory or path.suffix != '.jo':
                continue
            if (folder == 'std' and path.name in std_files) or folder == 'game':
                optional[folder][path.name] = names
            if folder == 'game':
                game_targets[path.name] = declared
    if missing := std_files - optional['std'].keys():
        raise ValueError(f'optional std files missing: {", ".join(sorted(missing))}')
    return Library(files, references, optional, game_targets)


def bucket(name: bytes, count: int) -> int:
    # Keep in step with std_file_for. The middle byte helps with __ prefixes.
    return (17 * name[0] + 31 * name[len(name) // 2] + 7 * name[-1] + len(name)) & (count - 1)


def encode(files: dict[str, set[str]], filenames: list[str], count: int,
           eager_names: set[str], game_targets: dict[str, dict[str, int]] | None,
           game_hooks: set[str]) -> tuple[bytes, bytes]:
    providers = Counter(name for names in files.values() for name in names)
    target_providers = Counter(
        (name, bit)
        for names in (game_targets or {}).values()
        for name, possible in names.items()
        for bit in TARGET_BITS.values()
        if possible & bit
    )
    groups: list[list[tuple[str, bytes]]] = [[] for _ in range(count)]
    for filename, names in sorted(files.items()):
        slot = filenames.index(filename)
        for name in sorted(names):
            # Keep every provider in the index. Shared families use the
            # existing bulk fallback rather than picking an arbitrary file.
            if game_targets is None:
                bulk = name in eager_names or providers[name] > 1
                route = bytes((slot | (128 if bulk else 0),))
            else:
                possible = game_targets[filename][name]
                # Other game files need the rest of the game's declarations registered first.
                mask = 0
                if name.startswith('__') and (filename in LAZY_GAME_MODULES or name in game_hooks):
                    mask = sum(bit for bit in TARGET_BITS.values()
                               if possible & bit and target_providers[name, bit] == 1)
                route = bytes((slot, mask))
            groups[bucket(name.encode(), count)].append((name, route))
    rows = bytearray()
    offsets = bytearray()
    for group in [*groups, []]:
        if len(rows) > 0xffff:
            raise ValueError('prelude index rows exceed the 16-bit bucket offsets')
        offsets += len(rows).to_bytes(2, 'little')
        for name, route in sorted(group):
            symbol = name.encode()
            if len(symbol) > 255:
                raise ValueError(f'prelude symbol is longer than one length byte: {name}')
            rows += bytes((len(symbol),)) + route + symbol
    return bytes(rows), bytes(offsets)


def jo_string(data: bytes) -> str:
    return '"' + ''.join(chr(byte) if 32 <= byte <= 126 and chr(byte) not in '"\\{}'
                         else f'\\x{byte:02x}' for byte in data) + '"'


def generated_block(library: Library) -> str:
    filenames = sorted(set(library.optional['std']) | set(library.optional['game']))
    if len(filenames) > 128:
        raise ValueError('the prelude index has more than 128 file IDs')
    eager_names = {
        name
        for path, names in library.files.items()
        if path.suffix == '.jo' and (
            path.parent == Path('lib/core')
            or (path.parent == Path('lib/std') and path.name not in library.optional['std'])
        )
        for name in names
    }
    non_game_names = set().union(*(library.files[path] for path in library.references))
    game_hooks = set().union(*library.references.values()) - non_game_names
    lines = [
        START,
        '# Run python3 tools/compiler/gen_prelude_index.py to update.',
        'const PRELUDE_FILES = [' + ', '.join(f'"{filename}"' for filename in filenames) + ']',
    ]
    for kind, count in (('std', 256), ('game', 1024)):
        targets = library.game_targets if kind == 'game' else None
        rows, offsets = encode(library.optional[kind], filenames, count, eager_names, targets, game_hooks)
        lines.append(f'const {kind.upper()}_FILE_SPEC = {jo_string(rows)}')
        lines.append(f'const {kind.upper()}_PREFIX_SPEC = {jo_string(offsets)}')
    return '\n'.join([*lines, END])


def replace_block(source: str, block: str) -> str:
    before, found, rest = source.partition(START)
    if not found or START in rest or rest.count(END) != 1:
        raise ValueError('compiler/prelude.jo must contain one generated prelude index block')
    return before + block + rest.partition(END)[2]


def read_index(source: str, *, game_target: str | None = None) -> dict[str, dict[str, set[str]]]:
    """Read the committed rows the lookup can reach, checking their buckets."""
    block = source.partition(START)[2].partition(END)[0]
    constants = dict(re.findall(r'^const ([A-Z_]+) = "(.*)"$', block, re.MULTILINE))

    def value(key: str) -> bytes:
        if key not in constants:
            raise ValueError(f'generated prelude index is missing {key}')
        return re.sub(rb'\\x([0-9a-f]{2})', lambda m: bytes((int(m[1], 16),)), constants[key].encode())

    file_array = re.search(r'^const PRELUDE_FILES = \[(.*)\]$', block, re.MULTILINE)
    if file_array is None:
        raise ValueError('generated prelude index is missing PRELUDE_FILES')
    filenames = re.findall(r'"([^"]+)"', file_array[1])
    index: dict[str, dict[str, set[str]]] = {}
    for kind in ('std', 'game'):
        header = 3 if kind == 'game' else 2
        names = value(f'{kind.upper()}_FILE_SPEC')
        offsets = value(f'{kind.upper()}_PREFIX_SPEC')
        starts = [int.from_bytes(offsets[i:i + 2], 'little') for i in range(0, len(offsets), 2)]
        count = len(starts) - 1
        if len(offsets) % 2 or count < 1 or count & (count - 1) or starts[0] != 0 or starts[-1] != len(names):
            raise ValueError(f'invalid {kind} prelude index bucket offsets')
        providers: dict[str, set[str]] = defaultdict(set)
        index[kind] = providers
        for partition, (start, stop) in enumerate(pairwise(starts)):
            if not start <= stop <= len(names):
                raise ValueError(f'invalid {kind} prelude index bucket offset {stop}')
            while start < stop:
                size = names[start]
                end = start + header + size
                if not size or end > stop:
                    raise ValueError(f'invalid {kind} prelude index record at {start}')
                file = names[start + 1] & 127
                if file >= len(filenames):
                    raise ValueError(f'invalid {kind} prelude index file ID at {start}')
                name = names[start + header:end]
                if bucket(name, count) != partition:
                    raise ValueError(f'{name.decode()} is in the wrong {kind} prelude index bucket')
                if kind == 'std' or game_target is None or names[start + 2] & TARGET_BITS[game_target]:
                    providers[name.decode()].add(filenames[file])
                start = end
    return index


def coverage_errors(library: Library, index: dict[str, dict[str, set[str]]]) -> list[str]:
    """Check all declared providers and references, conservatively by spelling."""
    missing: dict[str, set[Path]] = defaultdict(set)
    for kind, files in library.optional.items():
        for filename, names in files.items():
            for name in names:
                if filename not in index[kind].get(name, ()):
                    missing[name].add(Path('lib', kind, filename))
    errors = []
    for name, providers in sorted(missing.items()):
        for provider in sorted(providers):
            errors.append(f'{provider}: optional symbol {name} is missing from the prelude index')
            for path, words in library.references.items():
                if path != provider and name in words and name not in library.files[path]:
                    errors.append(f'{path}: cross-file reference to {name} in {provider} is missing from the prelude index')
    return errors


def check(root: Path, source: str) -> None:
    library = read_library(root, source)
    expected = replace_block(source, generated_block(library))
    errors = []
    if source != expected:
        errors.append('stale prelude index, run python3 tools/compiler/gen_prelude_index.py')
    try:
        errors.extend(coverage_errors(library, read_index(source)))
    except ValueError as error:
        errors.append(str(error))
    if errors:
        raise ValueError('\n'.join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail when the index needs regenerating')
    args = parser.parse_args()
    path = ROOT / 'compiler/prelude.jo'
    source = path.read_text(encoding='utf-8')
    try:
        if args.check:
            check(ROOT, source)
        else:
            updated = replace_block(source, generated_block(read_library(ROOT, source)))
            if updated != source:
                path.write_text(updated, encoding='utf-8')
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
