from os.path import commonpath, normpath
from pathlib import Path

CACHE_DIR_NAME = "__dewycache__"
EXTERNAL_DIR_NAME = "__external__"
HASH_DIGITS = 12

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3


def cache_source_rel(input_file: Path, *, cwd: Path | None = None) -> Path:
    """Return the cache-relative source key for an input file.

    Paths under cwd are mirrored (with a leading `__dewycache__/` stripped).
    Paths outside cwd go under `__external__/<12-hex>/<tail>`, where the hash
    is FNV-1a of the resolved absolute path and the tail is that path after
    the common ancestor with cwd.
    """
    here = Path.cwd()
    cwd = here if cwd is None else _abs(Path(cwd), here)
    abs_path = _abs(Path(input_file), cwd)
    try:
        rel = abs_path.relative_to(cwd)
    except ValueError:
        return _external_key(abs_path, cwd)
    if ".." in rel.parts:
        return _external_key(abs_path, cwd)
    return _strip_cache_prefix(rel)


def cache_layout(input_file: Path, *, cwd: Path | None = None) -> tuple[Path, str]:
    """Return `(cache_dir, input_name)` for `compile_and_link`."""
    rel = cache_source_rel(input_file, cwd=cwd)
    return Path(CACHE_DIR_NAME) / rel.parent, rel.stem


def cache_artifact(input_file: Path, suffix: str = "", *, cwd: Path | None = None) -> Path:
    """Return `__dewycache__/<mirrored-parent>/<stem><suffix>`."""
    cache_dir, name = cache_layout(input_file, cwd=cwd)
    return cache_dir / f"{name}{suffix}"


def path_hash12(path: Path) -> str:
    """12 lowercase hex digits of 64-bit FNV-1a over the posix path."""
    h = _FNV_OFFSET
    for byte in path.as_posix().encode():
        h ^= byte
        h = (h * _FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"[:HASH_DIGITS]


def _abs(path: Path, cwd: Path) -> Path:
    raw = path if path.is_absolute() else cwd / path
    return Path(normpath(raw))


def _external_key(abs_path: Path, cwd: Path) -> Path:
    return Path(EXTERNAL_DIR_NAME) / path_hash12(abs_path) / _external_tail(abs_path, cwd)


def _external_tail(abs_path: Path, cwd: Path) -> Path:
    common = Path(normpath(commonpath((str(abs_path), str(cwd)))))
    try:
        tail = abs_path.relative_to(common)
    except ValueError:
        return Path(abs_path.name)
    if tail == Path("."):
        return Path(abs_path.name)
    return tail


def _strip_cache_prefix(rel: Path) -> Path:
    parts = rel.parts
    if parts and parts[0] == CACHE_DIR_NAME:
        rest = parts[1:]
        if not rest:
            return Path(rel.name)
        return Path(*rest)
    return rel
