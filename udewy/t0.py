from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path

from .diagnostics import error

# ============================================================================
# Import preprocessing
# ============================================================================

char = str  # length=1

horizontal_whitespace: set[char] = {' ', '\t'}
vertical_whitespace: set[char] = {'\n', '\r'}
whitespace: set[char] = horizontal_whitespace | vertical_whitespace
DEFAULT_BACKENDS: tuple[str, ...] = ("x86_64", "wasm32", "riscv", "arm", "c")

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
            error(src, idx, "interpolation not supported in udewy strings")
        if src[idx] == "\\":
            idx += 1
            if idx >= len(src):
                error(src, idx, "unterminated string")
        idx += 1
    if idx >= len(src) or src[idx] != '"':
        error(src, idx, "unterminated string")
    return idx + 1


@dataclass(frozen=True)
class LoadedProgram:
    source: str
    link_artifacts: list[str]
    imported_sources: list[str]
    selected_backend: str = DEFAULT_BACKENDS[0]
    allowed_backends: list[str] = field(default_factory=lambda: list(DEFAULT_BACKENDS))


@dataclass
class _LoadState:
    imported_sources: set[Path]
    imported_artifacts: set[Path]
    selected_backend: str
    known_backends: tuple[str, ...]


def _make_state(
    imported_sources: set[Path] | None = None,
    selected_backend: str = DEFAULT_BACKENDS[0],
    known_backends: tuple[str, ...] = DEFAULT_BACKENDS,
) -> _LoadState:
    return _LoadState(
        imported_sources=set() if imported_sources is None else imported_sources,
        imported_artifacts=set(),
        selected_backend=selected_backend,
        known_backends=known_backends,
    )


def _consume_directive_line_end(src: str, idx: int, context: str) -> int:
    while idx < len(src) and src[idx] in horizontal_whitespace:
        idx += 1
    idx = skip_comment(src, idx)
    if idx < len(src) and src[idx] not in vertical_whitespace:
        error(src, idx, f"Unexpected trailing content after {context}")
    return skip_whitespace(src, idx)


def _skip_horizontal(src: str, idx: int) -> int:
    while idx < len(src) and src[idx] in horizontal_whitespace:
        idx += 1
    return idx


def _starts_keyword(src: str, idx: int, keyword: str) -> bool:
    if not src.startswith(keyword, idx):
        return False
    end_idx = idx + len(keyword)
    return end_idx >= len(src) or not is_ident(src[end_idx])


def _parse_string_value(src: str, idx: int, context: str) -> tuple[str, int]:
    if idx >= len(src) or src[idx] != '"':
        error(src, idx, f"Expected string literal {context}")
    end_idx = string_end(src, idx)
    return src[idx + 1 : end_idx - 1], end_idx


def _parse_string_value_list(
    src: str,
    idx: int,
    context: str,
    *,
    allow_empty: bool = False,
) -> tuple[list[str], int]:
    idx = skip_trivia(src, idx)
    if idx < len(src) and src[idx] == '"':
        value, idx = _parse_string_value(src, idx, context)
        return [value], idx

    if idx >= len(src) or src[idx] != "[":
        error(src, idx, f"Expected string literal or string array {context}")

    idx += 1
    values: list[str] = []
    while True:
        idx = skip_trivia(src, idx)
        if idx >= len(src):
            error(src, idx, f"Unterminated string array {context}")
        if src[idx] == "]":
            idx += 1
            if not values and not allow_empty:
                error(src, idx - 1, f"Expected at least one backend {context}")
            return values, idx

        value, idx = _parse_string_value(src, idx, context)
        values.append(value)


def _validate_backend_list(
    src: str,
    location: int,
    values: list[str],
    known_backends: tuple[str, ...],
    context: str,
) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    unknown: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
        if value not in known_backends and value not in unknown:
            unknown.append(value)

    if duplicates:
        error(src, location, f"Duplicate backend in {context}: {', '.join(duplicates)}")
    if unknown:
        error(
            src,
            location,
            f"Unknown backend in {context}: {', '.join(unknown)}. "
            f"Known backends: {', '.join(known_backends)}",
        )


def _parse_metatag_ref(src: str, idx: int) -> tuple[str, int]:
    if idx >= len(src) or src[idx] != "$":
        error(src, idx, "Expected metatag")

    name_start = idx + 1
    if name_start >= len(src) or not is_ident_start(src[name_start]):
        error(src, idx, "Expected metatag name after `$`")

    idx = name_start + 1
    while idx < len(src) and is_ident(src[idx]):
        idx += 1
    return src[name_start:idx], idx


def _parse_allowed_backends_assignment(
    src: str,
    idx: int,
    known_backends: tuple[str, ...],
) -> tuple[list[str], int] | None:
    if idx >= len(src) or src[idx] != "$":
        return None

    tag_location = idx
    name, idx = _parse_metatag_ref(src, idx)
    if name == "selected_backend":
        error(src, tag_location, "`$selected_backend` is read-only compiler metadata")
    if name != "allowed_backends":
        error(src, tag_location, f"Unknown metatag `${name}`")

    idx = _skip_horizontal(src, idx)
    if idx >= len(src) or src[idx] != "=":
        error(src, idx, "Expected `=` after `$allowed_backends`")

    values, idx = _parse_string_value_list(
        src,
        _skip_horizontal(src, idx + 1),
        "for `$allowed_backends`",
    )
    _validate_backend_list(src, tag_location, values, known_backends, "`$allowed_backends`")
    next_idx = _consume_directive_line_end(src, idx, "`$allowed_backends`")
    return values, next_idx


def _parse_initial_allowed_backends(
    src: str,
    known_backends: tuple[str, ...],
) -> tuple[list[str] | None, int, int]:
    directive_start = skip_trivia(src, 0)
    parsed_metatag = _parse_allowed_backends_assignment(src, directive_start, known_backends)
    if parsed_metatag is None:
        return None, 0, 0

    allowed_backends, next_idx = parsed_metatag
    return allowed_backends, directive_start, next_idx


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
        error(src, end_kw, "Expected path string after import")

    string_start = idx + 1
    end_idx = string_end(src, string_start)
    import_path = src[string_start + 1 : end_idx - 1]
    next_idx = _consume_directive_line_end(src, end_idx, "import")
    return import_path, next_idx


def _consume_in_operator(src: str, idx: int) -> int:
    idx = skip_trivia(src, idx)
    if not src.startswith("in?", idx):
        error(src, idx, "Expected `in?`")
    return idx + 3


def _parse_metatag_condition(
    src: str,
    idx: int,
    selected_backend: str,
    allowed_backends: list[str],
    known_backends: tuple[str, ...],
) -> tuple[bool, int]:
    idx = skip_trivia(src, idx)

    if idx < len(src) and src[idx] == "$":
        tag_location = idx
        name, idx = _parse_metatag_ref(src, idx)
        idx = skip_trivia(src, idx)
        if name != "selected_backend":
            error(src, tag_location, "Only `$selected_backend` may appear on the left side of a metatag condition")

        if src.startswith("=?", idx):
            value, idx = _parse_string_value(
                src,
                skip_trivia(src, idx + 2),
                "after `$selected_backend =?`",
            )
            _validate_backend_list(src, tag_location, [value], known_backends, "`$selected_backend =?`")
            return selected_backend == value, idx

        if src.startswith("in?", idx):
            values, idx = _parse_string_value_list(
                src,
                idx + 3,
                "after `$selected_backend in?`",
                allow_empty=True,
            )
            _validate_backend_list(src, tag_location, values, known_backends, "`$selected_backend in?`")
            return selected_backend in values, idx

        error(src, idx, "Expected `=?` or `in?` after `$selected_backend`")

    if idx < len(src) and src[idx] == '"':
        value, idx = _parse_string_value(src, idx, "before `in? $allowed_backends`")
        idx = _consume_in_operator(src, idx)
        idx = skip_trivia(src, idx)
        tag_location = idx
        name, idx = _parse_metatag_ref(src, idx)
        if name != "allowed_backends":
            error(src, tag_location, "Expected `$allowed_backends` after `in?`")
        _validate_backend_list(src, tag_location, [value], known_backends, "`in? $allowed_backends`")
        return value in allowed_backends, idx

    error(src, idx, "Expected metatag condition")


def _parse_conditional_import_block(
    src: str,
    idx: int,
    source_dir: Path,
    state: _LoadState,
    allowed_backends: list[str],
) -> tuple[LoadedProgram, int] | None:
    if not _starts_keyword(src, idx, "if"):
        return None

    condition_value, idx = _parse_metatag_condition(
        src,
        idx + 2,
        state.selected_backend,
        allowed_backends,
        state.known_backends,
    )
    idx = skip_trivia(src, idx)
    if idx >= len(src) or src[idx] != "{":
        error(src, idx, "Expected `{` after conditional import condition")
    idx += 1

    imported_source_parts: list[str] = []
    imported_source_paths: list[str] = []
    link_artifacts: list[str] = []

    while True:
        idx = skip_trivia(src, idx)
        if idx >= len(src):
            error(src, idx, "Unterminated conditional import block")
        if src[idx] == "}":
            next_idx = _consume_directive_line_end(src, idx + 1, "conditional import block")
            return LoadedProgram(
                "\n".join(imported_source_parts),
                link_artifacts,
                imported_source_paths,
                state.selected_backend,
                allowed_backends,
            ), next_idx

        parsed_import = _parse_import_directive(src, idx)
        if parsed_import is None:
            error(src, idx, "Only import directives are allowed inside conditional import blocks")

        import_path, idx = parsed_import
        if condition_value:
            loaded = _load_imported_path(import_path, source_dir, state)
            if loaded.source:
                imported_source_parts.append(loaded.source)
            link_artifacts.extend(loaded.link_artifacts)
            imported_source_paths.extend(loaded.imported_sources)


def _load_imported_path(
    import_path_str: str,
    source_dir: Path,
    state: _LoadState,
) -> LoadedProgram:
    import_path = (source_dir / import_path_str).resolve()
    if not import_path.exists():
        raise FileNotFoundError(f"Import file not found: {import_path}")

    if import_path.suffix == ".udewy":
        if import_path in state.imported_sources:
            return LoadedProgram("", [], [], state.selected_backend, list(state.known_backends))
        loaded = _load_program(import_path, state)
        return LoadedProgram(
            loaded.source,
            loaded.link_artifacts,
            [str(import_path), *loaded.imported_sources],
            state.selected_backend,
            loaded.allowed_backends,
        )

    if import_path in state.imported_artifacts:
        return LoadedProgram("", [], [], state.selected_backend, list(state.known_backends))

    state.imported_artifacts.add(import_path)
    return LoadedProgram("", [str(import_path)], [], state.selected_backend, list(state.known_backends))


def _load_program(source_path: Path, state: _LoadState) -> LoadedProgram:
    source_path = source_path.resolve()
    if source_path in state.imported_sources:
        return LoadedProgram("", [], [], state.selected_backend, list(state.known_backends))
    state.imported_sources.add(source_path)

    source = source_path.read_text()
    source_dir = source_path.parent
    declared_allowed_backends, metatag_start, idx = _parse_initial_allowed_backends(source, state.known_backends)
    allowed_backends = declared_allowed_backends if declared_allowed_backends is not None else list(state.known_backends)
    if state.selected_backend not in allowed_backends:
        error(
            source,
            0,
            f"Backend `{state.selected_backend}` is not allowed by {source_path}. "
            f"Allowed backends: {', '.join(allowed_backends)}",
        )

    imported_source_parts: list[str] = []
    imported_source_paths: list[str] = []
    link_artifacts: list[str] = []
    body_parts: list[str] = [source[:metatag_start]] if declared_allowed_backends is not None else []

    body_cursor = idx
    while True:
        idx = skip_trivia(source, idx)
        if idx >= len(source):
            break

        parsed_import = _parse_import_directive(source, idx)
        if parsed_import is not None:
            body_parts.append(source[body_cursor:idx])

            import_path, idx = parsed_import
            loaded = _load_imported_path(import_path, source_dir, state)
            if loaded.source:
                imported_source_parts.append(loaded.source)
            link_artifacts.extend(loaded.link_artifacts)
            imported_source_paths.extend(loaded.imported_sources)

            body_cursor = idx
            continue

        parsed_metatag = _parse_allowed_backends_assignment(source, idx, state.known_backends)
        if parsed_metatag is not None:
            error(source, idx, "`$allowed_backends` must appear before imports and conditional imports")

        parsed_conditional = _parse_conditional_import_block(
            source,
            idx,
            source_dir,
            state,
            allowed_backends,
        )
        if parsed_conditional is not None:
            body_parts.append(source[body_cursor:idx])
            loaded, idx = parsed_conditional
            if loaded.source:
                imported_source_parts.append(loaded.source)
            link_artifacts.extend(loaded.link_artifacts)
            imported_source_paths.extend(loaded.imported_sources)
            body_cursor = idx
            continue

        break

    body_parts.append(source[body_cursor:])
    combined_source = "\n".join([*imported_source_parts, "".join(body_parts)])
    return LoadedProgram(
        combined_source,
        link_artifacts,
        imported_source_paths,
        state.selected_backend,
        allowed_backends,
    )


def _resolve_load_options(
    source_path: Path,
    requested_backend: str | None,
    known_backends: list[str] | tuple[str, ...] | None,
) -> tuple[Path, str, tuple[str, ...]]:
    known_backend_names = tuple(DEFAULT_BACKENDS if known_backends is None else known_backends)
    if not known_backend_names:
        raise ValueError("known_backends must not be empty")
    if requested_backend is not None and requested_backend not in known_backend_names:
        raise ValueError(
            f"Unknown backend: {requested_backend}. Supported backends: {list(known_backend_names)}"
        )

    source_path = source_path.resolve()
    source = source_path.read_text()
    declared_allowed_backends, _, _ = _parse_initial_allowed_backends(source, known_backend_names)
    entry_allowed_backends = (
        declared_allowed_backends
        if declared_allowed_backends is not None
        else list(known_backend_names)
    )
    selected_backend = requested_backend if requested_backend is not None else entry_allowed_backends[0]
    if selected_backend not in entry_allowed_backends:
        error(
            source,
            0,
            f"Backend `{selected_backend}` is not allowed by {source_path}. "
            f"Allowed backends: {', '.join(entry_allowed_backends)}",
        )

    return source_path, selected_backend, known_backend_names


def load_program(
    source_path: PathLike,
    requested_backend: str | None = None,
    known_backends: list[str] | tuple[str, ...] | None = None,
) -> LoadedProgram:
    """
    Load the full udewy source and imported native link artifacts.

    Imports ending in `.udewy` are treated as udewy source and recursively
    prepended to the current file. Any other imported path is treated as a
    direct external artifact that should be handed to the backend linker.
    """

    source_path, selected_backend, known_backend_names = _resolve_load_options(
        Path(source_path),
        requested_backend,
        known_backends,
    )
    return _load_program(
        source_path,
        _make_state(
            selected_backend=selected_backend,
            known_backends=known_backend_names,
        ),
    )


def load_program_source(
    source_path: PathLike,
    imported: set[Path] | None = None,
    requested_backend: str | None = None,
    known_backends: list[str] | tuple[str, ...] | None = None,
) -> str:
    """
    Load the source code representing the entire program.
    Process leading import directives, recursively including imported files.
    Returns the combined source with imported content prepended to the entry point.
    """

    source_path, selected_backend, known_backend_names = _resolve_load_options(
        Path(source_path),
        requested_backend,
        known_backends,
    )
    return _load_program(
        source_path,
        _make_state(
            imported_sources=imported,
            selected_backend=selected_backend,
            known_backends=known_backend_names,
        ),
    ).source



# simple print out the fully expanded source given some entry point
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.t0 <file.udewy>")
        sys.exit(1)
    source_path = Path(sys.argv[1])
    source = load_program_source(source_path)
    print(source)