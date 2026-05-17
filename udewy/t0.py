from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from .diagnostics import error, warning

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


def skip_horizontal_whitespace(src: str, idx: int) -> int:
    while idx < len(src) and src[idx] in horizontal_whitespace:
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


@dataclass
class _LoadState:
    imported_sources: set[Path]
    imported_artifacts: set[Path]


@dataclass
class _PreludeContext:
    source: str
    source_path: Path
    source_dir: Path
    target_backend: str
    state: _LoadState
    imported_source_parts: list[str]
    imported_source_paths: list[str]
    link_artifacts: list[str]


def _make_state(imported_sources: set[Path] | None = None) -> _LoadState:
    return _LoadState(
        imported_sources=set() if imported_sources is None else imported_sources,
        imported_artifacts=set(),
    )


def _starts_with_name(src: str, idx: int, name: str) -> bool:
    if not src.startswith(name, idx):
        return False
    end_idx = idx + len(name)
    return end_idx >= len(src) or not is_ident(src[end_idx])


def _consume_directive_line_end(src: str, idx: int, context: str) -> int:
    idx = skip_horizontal_whitespace(src, idx)
    idx = skip_comment(src, idx)
    if idx < len(src) and src[idx] not in vertical_whitespace and src[idx] != "}":  # allowing '}' is so that conditional imports can be written on a single line. slightly muddies error messages for things like `import p"something" }` but keeping anyways to simplify the implementation.
        error(src, idx, f"Unexpected trailing content after {context}")
    return skip_whitespace(src, idx)


def _parse_import_directive(src: str, idx: int) -> tuple[str, int] | None:
    if not _starts_with_name(src, idx, "import"):
        return None

    end_kw = idx + 6
    idx = skip_horizontal_whitespace(src, end_kw)

    if idx >= len(src) or src[idx] != "p" or idx + 1 >= len(src) or src[idx + 1] != '"':
        error(src, end_kw, "Expected path string after import")

    string_start = idx + 1
    end_idx = string_end(src, string_start)
    import_path = src[string_start + 1 : end_idx - 1]
    next_idx = _consume_directive_line_end(src, end_idx, "import")
    return import_path, next_idx


def _parse_supported_targets(src: str, idx: int) -> tuple[set[str], int] | None:
    if not _starts_with_name(src, idx, "$supported_targets"):
        return None

    idx += len("$supported_targets")
    idx = skip_horizontal_whitespace(src, idx)
    if idx >= len(src) or src[idx] != "=":
        error(src, idx, "Expected '=' after $supported_targets")
    idx += 1

    idx = skip_horizontal_whitespace(src, idx)
    if idx >= len(src) or src[idx] != "[":
        error(src, idx, "Expected target list after $supported_targets =")
    idx += 1

    targets: set[str] = set()
    while True:
        idx = skip_trivia(src, idx)
        if idx < len(src) and src[idx] == "]":
            idx += 1
            break
        if idx >= len(src) or src[idx] != '"':
            error(src, idx, "Expected string target in $supported_targets list")
        end_idx = string_end(src, idx)
        targets.add(src[idx + 1 : end_idx - 1])
        idx = end_idx

    next_idx = _consume_directive_line_end(src, idx, "$supported_targets")
    return targets, next_idx


def _parse_if_target_condition(src: str, idx: int, target_backend: str) -> tuple[bool, int] | None:
    if not _starts_with_name(src, idx, "if"):
        return None

    idx = skip_trivia(src, idx + len("if"))
    if not _starts_with_name(src, idx, "$target"):
        error(src, idx, "Expected $target in preprocessor if")
    idx += len("$target")

    idx = skip_trivia(src, idx)
    if src.startswith("=?", idx):
        negate = False
        idx += 2
    elif src.startswith("not=?", idx):
        negate = True
        idx += 5
    else:
        error(src, idx, "Expected =? or not=? in preprocessor if")

    idx = skip_trivia(src, idx)
    if idx >= len(src) or src[idx] != '"':
        error(src, idx, "Expected string target in preprocessor if")
    end_idx = string_end(src, idx)
    condition_target = src[idx + 1 : end_idx - 1]
    active = target_backend == condition_target
    if negate:
        active = not active

    idx = skip_trivia(src, end_idx)
    if idx >= len(src) or src[idx] != "{":
        error(src, idx, "Expected '{' after preprocessor if condition")
    return active, idx + 1


def _skip_preprocessor_block(src: str, idx: int) -> int:
    depth = 1
    while idx < len(src):
        if src[idx] == '"':
            idx = string_end(src, idx)
            continue
        if src[idx] == "#":
            idx = skip_comment(src, idx)
            continue
        if src[idx] == "{":
            depth += 1
        elif src[idx] == "}":
            depth -= 1
            if depth == 0:
                return idx + 1
        idx += 1

    error(src, len(src), "Unterminated preprocessor if block")


def _parse_meta_diagnostic(src: str, idx: int) -> tuple[str, str, int, int] | None:
    start = idx
    if _starts_with_name(src, idx, "$warning"):
        kind = "warning"
        idx += len("$warning")
    elif _starts_with_name(src, idx, "$error"):
        kind = "error"
        idx += len("$error")
    else:
        return None

    idx = skip_horizontal_whitespace(src, idx)
    if idx >= len(src) or src[idx] != "(":
        error(src, idx, f"Expected '(' after ${kind}")
    idx += 1

    idx = skip_horizontal_whitespace(src, idx)
    if idx >= len(src) or src[idx] != '"':
        error(src, idx, f"Expected string message in ${kind}")
    end_idx = string_end(src, idx)
    message = src[idx + 1 : end_idx - 1]

    idx = skip_horizontal_whitespace(src, end_idx)
    if idx >= len(src) or src[idx] != ")":
        error(src, idx, f"Expected ')' after ${kind} message")
    idx += 1

    next_idx = _consume_directive_line_end(src, idx, f"${kind}")
    return kind, message, start, next_idx


def _process_prelude_block(ctx: _PreludeContext, idx: int) -> int:
    src = ctx.source
    while True:
        idx = skip_trivia(src, idx)
        if idx >= len(src):
            error(src, len(src), "Unterminated preprocessor if block")
        if src[idx] == "}":
            return idx + 1

        next_idx = _process_prelude_item(ctx, idx)
        if next_idx is None:
            error(src, idx, "Expected preprocessor directive or '}' in preprocessor if block")
        idx = next_idx


def _process_prelude_item(ctx: _PreludeContext, idx: int) -> int | None:
    src = ctx.source

    parsed_import = _parse_import_directive(src, idx)
    if parsed_import is not None:
        import_path, next_idx = parsed_import
        loaded = _load_imported_path(import_path, ctx.source_dir, ctx.target_backend, ctx.state)
        if loaded.source:
            ctx.imported_source_parts.append(loaded.source)
        ctx.link_artifacts.extend(loaded.link_artifacts)
        ctx.imported_source_paths.extend(loaded.imported_sources)
        return next_idx

    parsed_targets = _parse_supported_targets(src, idx)
    if parsed_targets is not None:
        targets, next_idx = parsed_targets
        if ctx.target_backend not in targets:
            supported = ", ".join(sorted(targets))
            error(
                src,
                idx,
                f"{ctx.source_path} supports targets: {supported}; current target is {ctx.target_backend}",
            )
        return next_idx

    parsed_if = _parse_if_target_condition(src, idx, ctx.target_backend)
    if parsed_if is not None:
        active, block_start = parsed_if
        if active:
            block_end = _process_prelude_block(ctx, block_start)
        else:
            block_end = _skip_preprocessor_block(src, block_start)
        return _consume_directive_line_end(src, block_end, "preprocessor if")

    parsed_diagnostic = _parse_meta_diagnostic(src, idx)
    if parsed_diagnostic is not None:
        kind, message, start, next_idx = parsed_diagnostic
        if kind == "warning":
            warning(message, src, start)
        else:
            error(src, start, message)
        return next_idx

    return None


def _load_imported_path(
    import_path_str: str,
    source_dir: Path,
    target_backend: str,
    state: _LoadState,
) -> LoadedProgram:
    import_path = (source_dir / import_path_str).resolve()
    if not import_path.exists():
        raise FileNotFoundError(f"Import file not found: {import_path}")

    if import_path.suffix == ".udewy":
        if import_path in state.imported_sources:
            return LoadedProgram("", [], [])
        loaded = _load_program(import_path, target_backend, state)
        return LoadedProgram(
            loaded.source,
            loaded.link_artifacts,
            [str(import_path), *loaded.imported_sources],
        )

    if import_path in state.imported_artifacts:
        return LoadedProgram("", [], [])

    state.imported_artifacts.add(import_path)
    return LoadedProgram("", [str(import_path)], [])


def _load_program(source_path: Path, target_backend: str, state: _LoadState) -> LoadedProgram:
    source_path = source_path.resolve()
    if source_path in state.imported_sources:
        return LoadedProgram("", [], [])
    state.imported_sources.add(source_path)

    source = source_path.read_text()
    source_dir = source_path.parent
    imported_source_parts: list[str] = []
    imported_source_paths: list[str] = []
    link_artifacts: list[str] = []
    body_parts: list[str] = []
    ctx = _PreludeContext(
        source=source,
        source_path=source_path,
        source_dir=source_dir,
        target_backend=target_backend,
        state=state,
        imported_source_parts=imported_source_parts,
        imported_source_paths=imported_source_paths,
        link_artifacts=link_artifacts,
    )

    idx = 0
    body_cursor = 0
    while True:
        idx = skip_trivia(source, idx)
        if idx >= len(source):
            break

        next_idx = _process_prelude_item(ctx, idx)
        if next_idx is None:
            break

        body_parts.append(source[body_cursor:idx])
        idx = next_idx
        body_cursor = idx

    body_parts.append(source[body_cursor:])
    combined_source = "\n".join([*imported_source_parts, "".join(body_parts)])
    return LoadedProgram(combined_source, link_artifacts, imported_source_paths)


def load_program(
    source_path: PathLike,
    target_backend: str = "x86_64",
) -> LoadedProgram:
    """
    Load the full udewy source and imported native link artifacts.

    Imports ending in `.udewy` are treated as udewy source and recursively
    prepended to the current file. Any other imported path is treated as a
    direct external artifact that should be handed to the backend linker.
    """

    return _load_program(Path(source_path), target_backend, _make_state())


def load_program_source(
    source_path: PathLike,
    imported: set[Path] | None = None,
    target_backend: str = "x86_64",
) -> str:
    """
    Load the source code representing the entire program.
    Process leading import directives, recursively including imported files.
    Returns the combined source with imported content prepended to the entry point.
    """
    
    return _load_program(Path(source_path), target_backend, _make_state(imported)).source



# simple print out the fully expanded source given some entry point
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.t0 <file.udewy>")
        sys.exit(1)
    source_path = Path(sys.argv[1])
    source = load_program_source(source_path)
    print(source)