"""Format patterns and `fmt` on source with multi-byte characters next to operators, and on bytes that are not UTF-8, never
panics: an operator's length can end inside the character that follows it."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCES = {
    'main.dewy': 'main=():>void=>{\n    let é=1\n    let x=é+é\n    let y=é .+= 2\n    let z=é**é\n'
                 '    printl(x+中 y**é z.+=😀)\n}\n',
    'legacy.jo': 'main = () -> int:\n    é = 1\n    x = é+é\n    z = é**é\n    return x+中\n',
    'stray.dewy': b'a=1\n\x80=2\nx=a+\x80 +\xbf\nb=a**\xc3\n',
}


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_fmt_does_not_panic(compiler, tmp_path, name):
    source = SOURCES[name]
    path = tmp_path / name
    path.write_bytes(source if isinstance(source, bytes) else source.encode())
    for arguments in (['fmt', str(path)], ['fmt', '--check', str(path)]):
        done = subprocess.run([compiler, *arguments], capture_output=True, timeout=60, cwd=tmp_path)
        message = done.stderr.decode('utf-8', 'replace')
        assert done.returncode >= 0 and 'panic' not in message, message


PATTERNS = {
    'format_pattern_wide_type': 'main=():>void=>{\n    let s=fmt"é"(1)\n    let t=fmt"中d"(1.5)\n    let u=fmt"d😀"(1)\n}\n',
    'format_pattern_wide_precision': "main=():>void=>{printl(fmt'.9999999é999999999999999f'(1.25))}\n",
    'format_pattern_stray_byte': b'main=():>void=>{printl(fmt"\x80"(1) fmt"d\xbf"(2))}\n',
}


@pytest.mark.parametrize('name', sorted(PATTERNS))
def test_format_patterns_do_not_panic(compiler, tmp_path, name):
    """A pattern the checker reads while compiling, with a character or stray byte where a type belongs."""
    source = PATTERNS[name]
    path = tmp_path / 'main.dewy'
    path.write_bytes(source if isinstance(source, bytes) else source.encode())
    done = subprocess.run([compiler, str(path)], capture_output=True, timeout=60, cwd=tmp_path)
    message = done.stderr.decode('utf-8', 'replace')
    assert done.returncode >= 0 and 'panic' not in message, message
