import sys
from typing import NoReturn


def format_source_context(src: str, location: int, message: str = "", context_lines: int = 1) -> str:
    """
    Render the source line containing `location` (a character offset into `src`)
    with a leading line number, the offending line, and a caret at the column.
    Optionally include `context_lines` of surrounding lines for extra context.
    """
    location = max(0, min(location, len(src)))

    line_start = src.rfind('\n', 0, location) + 1
    line_end = src.find('\n', location)
    if line_end == -1:
        line_end = len(src)

    line_num = src.count('\n', 0, location) + 1
    col = location - line_start

    pre_start = line_start
    for _ in range(context_lines):
        prev = src.rfind('\n', 0, pre_start - 1)
        if prev < 0:
            pre_start = 0
            break
        pre_start = prev + 1

    post_end = line_end
    for _ in range(context_lines):
        nxt = src.find('\n', post_end + 1)
        if nxt < 0:
            post_end = len(src)
            break
        post_end = nxt

    pre_text = src[pre_start:line_start]
    line_text = src[line_start:line_end]
    post_text = src[line_end + 1:post_end] if line_end < len(src) else ""

    pre_first_lineno = line_num - pre_text.count('\n') if pre_text else line_num
    last_lineno = line_num + (post_text.count('\n') + 1 if post_text else 0)
    width = len(str(last_lineno))

    out: list[str] = []
    if message:
        out.append(f"{message} (line {line_num}, column {col + 1})")
    else:
        out.append(f"line {line_num}, column {col + 1}")

    n = pre_first_lineno
    for ln in pre_text.splitlines():
        out.append(f"{n:>{width}} | {ln}")
        n += 1

    prefix = f"{line_num:>{width}} | "
    out.append(f"{prefix}{line_text}")
    out.append(f"{' ' * len(prefix)}{' ' * col}^")

    n = line_num + 1
    for ln in post_text.splitlines():
        out.append(f"{n:>{width}} | {ln}")
        n += 1

    return "\n".join(out)


def error(src: str, location: int, message: str) -> NoReturn:
    """
    Raise a SyntaxError whose message is `message` plus the formatted source
    context pointing at `location`.
    """
    raise SyntaxError(format_source_context(src, location, message))


def warning(message: str, src: str | None = None, location: int | None = None) -> None:
    """
    Emit a non-fatal diagnostic to stderr.

    If both `src` and `location` are provided, the warning is rendered with the
    same source-context block used by `error`. Otherwise it is printed as a
    plain `warning: ...` line.
    """
    if src is not None and location is not None:
        body = format_source_context(src, location, f"warning: {message}")
    else:
        body = f"warning: {message}"
    print(body, file=sys.stderr)
