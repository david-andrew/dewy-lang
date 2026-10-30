"""`text.get(i)` is a grapheme or none, as `xs.get(i)` is for arrays."""
import subprocess

from tests.support import compiler  # noqa: F401


def run(compiler, tmp_path, source):
    path = tmp_path / 'get.dewy'
    path.write_text(source)
    checked = subprocess.run([compiler, 'check', '--obligations', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert 'runtime check:' not in checked.stdout
    out = tmp_path / 'get'
    built = subprocess.run([compiler, 'build', path, '-o', out], text=True, capture_output=True, timeout=60)
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([out], text=True, capture_output=True, timeout=10)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    return ran.stdout


def test_string_get_graphemes_and_ends(compiler, tmp_path):
    source = '''main = () => {
    let text = "cafe\\u{301}🙂!"
    let shown = [loop i in [-1..7) text.get(i) ?? "_"]
    printl(shown.join("|"))
    let huge:int = 99999999999999999999999
    printl(text.get(huge) ?? "none")
    printl("".get(0) ?? "empty")
}
'''
    assert run(compiler, tmp_path, source) == '_|c|a|f|é|🙂|!|_\nnone\nempty\n'


def test_string_get_scans_without_guards(compiler, tmp_path):
    source = '''skip = (text:string start:int):>int => {
    let i = start
    loop text.get(i) =? " " i += 1
    i
}
main = () => printl(skip("   x" 0) skip("ab" 5) skip("a b" -3))
'''
    assert run(compiler, tmp_path, source) == '3 5 -3\n'


def test_string_index_still_needs_bounds(compiler, tmp_path):
    path = tmp_path / 'index.dewy'
    path.write_text('f = (text:string i:int):>string => text[i]\n')
    checked = subprocess.run([compiler, 'check', path], text=True, capture_output=True, timeout=60)
    assert checked.returncode != 0
    assert 'index' in checked.stdout + checked.stderr, checked.stdout + checked.stderr
