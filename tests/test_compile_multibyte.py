"""Compile errors, hints and format patterns on multi-byte text, and on bytes that are not UTF-8, never
panic: an offset can fall inside a character (or on a stray continuation byte) where a hint or the
reader cuts the source."""
import subprocess

import pytest

from tests.support import compiler  # noqa: F401

SOURCES = {
    # (a stray continuation byte begins the token after an arrow)
    'stray_byte_after_arrow': b'f = (g:int):>int =>\x80 1\nmain = () => printl(f(1))\n',
    'stray_byte_in_metatag': b'$assume_loc\xbfal_asserts=false\nmain=()=>printl(1)\n',
    'stray_byte_after_name': b'main = () => {\n    let x = 3\n    if x >? 2 { printl"big" } elif x >? 1 { printl"mid"\x80 }\n}\n',
    'wide_text_after_habit': 'main = () => {\n    let x = 3\n    if x >? 2 { printl"big" } elif x >? 1 { printl"mid中" }\n}\n',
    'wide_names': 'Écran:type=[x:int64]\nmain=():>void=>{\n    let n:Écran=3\n    let é=[1 2]\n    é.append(1)\n    printl(é.png é.中 é.lenght)\n}\n',
    'wide_assertion': 'main=():>void=>{\n    let é=1\n    $runtime_assert é =? 2\n    $runtime_assert é+é =? 3 and 中 =? 1\n}\n',
    'wide_conversion': 'main=():>void=>{\n    let é=3.5\n    let x:uint8=int64(é)\n    let y:int64=é\n}\n',
    'wide_call_hints': 'main=():>void=>{\n    let é=1\n    printl(é.tweens.add(1) é.pngé)\n    this.tweensé.add(1)\n    printl(cat1.png 😀.wav)\n}\n',
    'wide_unit': 'main=():>void=>{\n    let m=1\n    let x=9.81 é\n    let y=3 中 m\n}\n',
    'stray_bytes_everywhere': b'\x80main=():>void=>{\n\xbf\n    let \x80a=1\n    printl(\x80a \xbf\xbf)\n}\n',
}


@pytest.mark.parametrize('name', sorted(SOURCES))
def test_compile_errors_do_not_panic(compiler, tmp_path, name):
    source = SOURCES[name]
    path = tmp_path / 'main.dewy'
    path.write_bytes(source if isinstance(source, bytes) else source.encode())
    done = subprocess.run([compiler, str(path)], capture_output=True, timeout=60, cwd=tmp_path)
    message = done.stderr.decode('utf-8', 'replace')
    assert done.returncode >= 0, message
    assert 'panic' not in message and 'does not start and end on char boundaries' not in message, message
