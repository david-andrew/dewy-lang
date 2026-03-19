from dataclasses import dataclass
from os import PathLike
from pathlib import Path

# ============================================================================
# Import preprocessing
# ============================================================================

char = str  # length=1

horizontal_whitespace: set[char] = {' ', '\t'}
vertical_whitespace: set[char] = {'\n', '\r'}
whitespace: set[char] = horizontal_whitespace | vertical_whitespace

def is_alpha(c: char) -> bool:
    return ('A' <= c <= 'Z') or ('a' <= c <= 'z')

def is_digit(c: char) -> bool:
    return '0' <= c <= '9'


def is_ident_start(c: char) -> bool:
    return is_alpha(c) or c == '_'


def is_ident(c: char) -> bool:
    return is_ident_start(c) or is_digit(c)


def is_hex(c: char) -> bool:
    return is_digit(c) or ("A" <= c <= "F") or ("a" <= c <= "f")


def hex_value(c: char) -> int:
    if "0" <= c <= "9":
        return ord(c) - ord("0")
    if "A" <= c <= "F":
        return ord(c) - ord("A") + 10
    if "a" <= c <= "f":
        return ord(c) - ord("a") + 10
    raise ValueError(f"invalid hex digit: {c}")


def skip_whitespace(src: str, idx: int) -> int:
    while idx < len(src) and src[idx] in whitespace:
        idx += 1
    return idx


def skip_comment(src: str, idx: int) -> int:
    if idx < len(src) and src[idx] == "#":
        idx += 1
        while idx < len(src) and src[idx] != "\n":
            idx += 1
    return idx


def skip_trivia(src: str, idx: int) -> int:
    while idx < len(src):
        next_idx = skip_comment(src, skip_whitespace(src, idx))
        if next_idx == idx:
            return idx
        idx = next_idx
    return idx


def string_end(src: str, start: int) -> int:
    assert src[start] == '"', f"INTERNAL ERROR: Expected string at position {start}"

    idx = start + 1
    while idx < len(src) and src[idx] != '"':
        if src[idx] in "{}":
            raise SyntaxError(f"interpolation not supported in udewy strings at {idx}: {src[start:idx]!r}")
        if src[idx] == "\\":
            idx += 1
            if idx >= len(src):
                raise SyntaxError(f"unterminated string at {idx}: {src[start:idx]!r}")
        idx += 1
    if idx >= len(src) or src[idx] != '"':
        raise SyntaxError(f"unterminated string at {idx}: {src[start:idx]!r}")
    return idx + 1


@dataclass(frozen=True)
class LoadedProgram:
    source: str
    link_artifacts: list[str]
    link_flags: list[str]


META_DIRECTIVES: dict[str, tuple[str, ...]] = {
    "cc_pthread": ("-pthread",),
    "cc_lm": ("-lm",),
}


@dataclass
class _LoadState:
    imported_sources: set[Path]
    imported_artifacts: set[Path]
    imported_link_flags: set[str]


def _make_state(imported_sources: set[Path] | None = None) -> _LoadState:
    return _LoadState(
        imported_sources=set() if imported_sources is None else imported_sources,
        imported_artifacts=set(),
        imported_link_flags=set(),
    )


def _consume_directive_line_end(src: str, idx: int, context: str) -> int:
    while idx < len(src) and src[idx] in horizontal_whitespace:
        idx += 1
    idx = skip_comment(src, idx)
    if idx < len(src) and src[idx] not in vertical_whitespace:
        raise SyntaxError(f"Unexpected trailing content after {context} at position {idx}")
    return skip_whitespace(src, idx)


def _parse_import_directive(src: str, idx: int) -> tuple[str, int] | None:
    if not src.startswith("import", idx):
        return None

    end_kw = idx + 6
    if end_kw < len(src) and is_ident(src[end_kw]):
        return None

    idx = end_kw
    while idx < len(src) and src[idx] in horizontal_whitespace:
        idx += 1

    if idx >= len(src) or src[idx] != "p" or idx + 1 >= len(src) or src[idx + 1] != '"':
        raise SyntaxError(f"Expected path string after import at position {end_kw}")

    string_start = idx + 1
    end_idx = string_end(src, string_start)
    import_path = src[string_start + 1 : end_idx - 1]
    next_idx = _consume_directive_line_end(src, end_idx, "import")
    return import_path, next_idx


def _parse_meta_directive(src: str, idx: int) -> tuple[str, int] | None:
    if idx >= len(src) or src[idx] != "$":
        return None

    idx += 1
    if idx >= len(src) or not is_ident_start(src[idx]):
        raise SyntaxError(f"Expected meta directive name after $ at position {idx}")

    name_start = idx
    idx += 1
    while idx < len(src) and is_ident(src[idx]):
        idx += 1

    directive = src[name_start:idx]
    next_idx = _consume_directive_line_end(src, idx, "meta directive")
    return directive, next_idx


def _load_imported_path(
    import_path_str: str,
    source_dir: Path,
    state: _LoadState,
) -> LoadedProgram:
    import_path = (source_dir / import_path_str).resolve()
    if not import_path.exists():
        raise FileNotFoundError(f"Import file not found: {import_path}")

    if import_path.suffix == ".udewy":
        return _load_program(import_path, state)

    if import_path in state.imported_artifacts:
        return LoadedProgram("", [], [])

    state.imported_artifacts.add(import_path)
    return LoadedProgram("", [str(import_path)], [])


def _load_meta_directive(directive: str, state: _LoadState) -> list[str]:
    flags = META_DIRECTIVES.get(directive)
    if flags is None:
        raise SyntaxError(f"Unknown udewy meta directive ${directive}")

    new_flags: list[str] = []
    for flag in flags:
        if flag not in state.imported_link_flags:
            state.imported_link_flags.add(flag)
            new_flags.append(flag)
    return new_flags


def _load_program(source_path: Path, state: _LoadState) -> LoadedProgram:
    source_path = source_path.resolve()
    if source_path in state.imported_sources:
        return LoadedProgram("", [], [])
    state.imported_sources.add(source_path)

    source = source_path.read_text()
    source_dir = source_path.parent
    imported_sources: list[str] = []
    link_artifacts: list[str] = []
    link_flags: list[str] = []
    body_parts: list[str] = []

    idx = 0
    body_cursor = 0
    while True:
        idx = skip_trivia(source, idx)
        if idx >= len(source):
            break

        parsed_import = _parse_import_directive(source, idx)
        parsed_meta = None if parsed_import is not None else _parse_meta_directive(source, idx)
        if parsed_import is None and parsed_meta is None:
            break

        body_parts.append(source[body_cursor:idx])

        if parsed_import is not None:
            import_path, idx = parsed_import
            loaded = _load_imported_path(import_path, source_dir, state)
            if loaded.source:
                imported_sources.append(loaded.source)
            link_artifacts.extend(loaded.link_artifacts)
            link_flags.extend(loaded.link_flags)
        else:
            directive, idx = parsed_meta
            link_flags.extend(_load_meta_directive(directive, state))

        body_cursor = idx

    body_parts.append(source[body_cursor:])
    combined_source = "\n".join([*imported_sources, "".join(body_parts)])
    return LoadedProgram(combined_source, link_artifacts, link_flags)


def load_program(
    source_path: PathLike,
) -> LoadedProgram:
    """
    Load the full udewy source, imported native link artifacts, and top-level
    meta link directives.

    Imports ending in `.udewy` are treated as udewy source and recursively
    prepended to the current file. Any other imported path is treated as a
    direct external artifact that should be handed to the backend linker.
    Leading `$...` meta directives are expanded into backend link flags.
    """

    return _load_program(Path(source_path), _make_state())


def load_program_source(source_path: PathLike, imported: set[Path] | None = None) -> str:
    """
    Load the source code representing the entire program.
    Process leading import directives, recursively including imported files.
    Returns the combined source with imported content prepended to the entry point.
    """
    
    return _load_program(Path(source_path), _make_state(imported)).source



# simple print out the fully expanded source given some entry point
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.t0 <file.udewy>")
        sys.exit(1)
    source_path = Path(sys.argv[1])
    source = load_program_source(source_path)
    print(source)