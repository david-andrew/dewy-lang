from pathlib import Path
from os import PathLike

# ============================================================================
# Import preprocessing
# ============================================================================

char = str  # length=1

horizontal_whitespace: set[char] = {' ', '\t'}
vertical_whitespace: set[char] = {'\n', '\r'}
whitespace: set[char] = horizontal_whitespace | vertical_whitespace

def is_alpha(c:char)->bool:
    return ('A' <= c <= 'Z') or ('a' <= c <= 'z')

def is_digit(c:char)->bool:
    return '0' <= c <= '9'

def digit_value(c: char) -> int:
    if '0' <= c <= '9':
        return ord(c) - ord('0')
    raise ValueError(f"invalid digit: {c}")

def is_hex(c: char)->bool:
    return is_digit(c) or ('A' <= c <= 'F') or ('a' <= c <= 'f')

def hex_value(c: char) -> int:
    if '0' <= c <= '9':
        return ord(c) - ord('0')
    if 'A' <= c <= 'F':
        return ord(c) - ord('A') + 10
    if 'a' <= c <= 'f':
        return ord(c) - ord('a') + 10
    
    raise ValueError(f"invalid hex digit: {c}")

def is_ident(c: char) -> bool:
    """check if a character is a valid identifier (body) character, i.e. alpha, digit, or underscore"""
    return is_alpha(c) or is_digit(c) or c == '_'


def skip_whitespace(src:str, idx:int) -> int:
    while idx < len(src) and src[idx] in whitespace:
        idx += 1
    return idx

def skip_comment(src:str, idx:int) -> int:
    if idx >= len(src):
        return idx
    if src[idx] == '#':
        idx += 1
        while idx < len(src) and src[idx] != '\n':
            idx += 1
    return idx

def skip_trivia(src:str, idx:int) -> int:
    while idx < len(src):
        start = idx
        idx = skip_whitespace(src, idx)
        idx = skip_comment(src, idx)
        if idx == start:
            break
    return idx

def string_end(src:str, start:int) -> int:
    assert src[start] == '"', f"INTERNAL ERROR: Expected string at position {start}"
    
    i = start + 1
    while i < len(src) and src[i] != '"':
        if src[i] == '{' or src[i] == '}': raise SyntaxError(f"interpolation not supported in udewy strings at {i}: {src[start:i]!r}")
        if src[i] == '\\':
            i += 1
            if i >= len(src):
                raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
        i += 1
    if i >= len(src) or src[i] != '"':
        raise SyntaxError(f"unterminated string at {i}: {src[start:i]!r}")
    i += 1
    return i


def load_program_source(source_path: PathLike, imported: set[Path] | None = None) -> str:
    """
    Load the source code representing the entire program.
    Process leading import directives, recursively including imported files.
    Returns the combined source with imported content prepended to the entry point.
    """
    
    if imported is None:
        imported = set()
    
    # check if we already processed this file
    source_path = Path(source_path).resolve()
    if source_path in imported:
        return ""
    imported.add(source_path)
    
    source = source_path.read_text()
    source_dir = source_path.parent
    result_parts: list[str] = []
    body_parts: list[str] = []

    i = 0
    body_cursor = 0
    n = len(source)

    while True:
        i = skip_trivia(source, i)
        if i >= n:
            break

        if not source.startswith('import', i):
            break

        end_kw = i + 6
        if end_kw < n and is_ident(source[end_kw]): #i.e. not `import` because it's a longer identifier
            break

        body_parts.append(source[body_cursor:i])

        i = end_kw
        while i < n and source[i] in horizontal_whitespace:
            i += 1

        # collect the path string `p"..."`
        if i >= n or source[i] != 'p' or i + 1 >= n or source[i + 1] != '"':
            raise SyntaxError(f"Expected path string after import at position {end_kw}")
        path_start = i + 1
        i = string_end(source, path_start)
        import_path_str = source[path_start+1:i-1] # strip the quotes

        # should only be trivia after path string before line end
        while i < n and source[i] in horizontal_whitespace:
            i += 1
        i = skip_comment(source, i)
        if i < n and source[i] not in vertical_whitespace:
            raise SyntaxError(f"Unexpected trailing content after import at position {i}")
        i = skip_whitespace(source, i)

        # resolve the path to the import file
        import_path = (source_dir / import_path_str).resolve()
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")

        # read the import file and recursively process its imports
        processed_import = load_program_source(import_path, imported)
        if processed_import:
            result_parts.append(processed_import)

        # start after the import directive and any trivia
        body_cursor = i

    body_parts.append(source[body_cursor:])
    result_parts.append(''.join(body_parts))
    
    return '\n'.join(result_parts)



# simple print out the fully expanded source given some entry point
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m udewy.t0 <file.udewy>")
        sys.exit(1)
    source_path = Path(sys.argv[1])
    source = load_program_source(source_path)
    print(source)