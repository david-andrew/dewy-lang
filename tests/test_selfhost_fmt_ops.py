"""`dewy-core fmt` agrees with frozen Jo: layout, token checks, --check, stdin and directory walks."""
import re
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

# Implementation-language text the layout rules reach: tabs, odd indentation, comments at columns,
# unary signs, array elements, units, dotted operators, and=, continuations, blank-line runs, CRLF
SAMPLES = {
    'layout.jo': 'main=()->int:\n  x=[1 -2, 3]\n\tif x[0]>0 and( x[1]<0 ):   # a note\n\t    return -x[0]*2\n\n\n\n'
                 '  # a comment line\n  y = 9.81(m/s^2)+ [1 2](mm)\n  z=a .+ b .== c\n  ok and= true\n'
                 '  w = f(1)[ 2 ]   \\\n      + g( 3 )\n  return x . len()\n',
    'nested.jo': 'f = (a: int,b:int)->int:\n    loop i in [0..a):\n          if i%2==0 :\n                 b+=i\n'
                 '          # moved with its block\n    return b ?? 0\n',
    'crlf.jo': 'g = ()->str:\r\n  s = "a\r\nb"\r\n  return s\r\n',
    'refused.jo': 'r = ():\n    x = [1 -2, - 3]\n    f (1)\n',
    'bad.jo': 'h = ():\n    x = 1\n  y = 2\n',
    'nolex.jo': 'k = ():\n    s = "unterminated\n',
    'model.dewy': '\tmain=()=>{\nlet x:int64=20\n if x>?0{\n return x+22   # keep\n }\nreturn 0\n}',
    'broken.dewy': 'main=()=>[42}',
}


def perturbed(text):
    """Real source with its spacing disturbed: halved indentation, spaces removed around = and after
    commas, spaces added before closing brackets and at line ends."""
    out = []
    for line in text.split('\n'):
        body = line.lstrip(' ')
        out.append(' ' * ((len(line) - len(body)) // 2) + body)
    text = '\n'.join(out)
    text = re.sub(r' = (?=\w)', '=', text)
    text = text.replace(', ', ',').replace(')\n', ' )  \n')
    return text


def run(binary, cwd, *args, **options):
    result = subprocess.run([binary, 'fmt', *args], cwd=cwd, capture_output=True, text=True,
                            timeout=120, check=False, **options)
    return result.returncode, result.stdout, result.stderr.replace(str(binary), 'dewy-core')


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob('*')) if p.is_file()}


def write_inputs(root):
    root.mkdir()
    for name, text in SAMPLES.items():
        (root / name).write_bytes(text.encode())
    (root / 'real').mkdir()
    for name in ('fmt.jo', 'lex.jo', 'ide.jo', 'watch.jo'):
        (root / 'real' / name).write_text(perturbed((ROOT / 'compiler' / name).read_text()))
    (root / 'real' / 'build').mkdir()
    (root / 'real' / 'build' / 'skipped.jo').write_text('x=1\n')


def outcome(binary, tmp_path, label):
    root = tmp_path / label
    write_inputs(root)
    results = [run(binary, root, '--check', '.'),
               run(binary, root, 'layout.jo', 'nested.jo', 'crlf.jo', 'bad.jo', 'refused.jo',
                   'model.dewy'),
               run(binary, root, 'nolex.jo'),
               run(binary, root, 'broken.dewy'),
               run(binary, root, 'real'),
               run(binary, root, '-', input=SAMPLES['model.dewy']),
               run(binary, root),
               run(binary, root, 'missing.jo')]
    return results, tree(root)


def test_fmt_ops_matches_twin(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    dewy, jo = leaf_compilers(compiler, tmp_path, ('fmt_ops',))
    expected = outcome(jo, tmp_path, 'jo')
    assert outcome(dewy, tmp_path, 'dewy') == expected
    results, files = expected
    # (the inputs reached each path: changes, a check failure, refusals and a clean rerun)
    assert results[0][0] == 1 and 'layout.jo' in results[0][1]
    assert files['layout.jo'] != SAMPLES['layout.jo'].encode() and b'\r\n' in files['crlf.jo']
    assert files['bad.jo'] == SAMPLES['bad.jo'].encode() and results[3][0] == 1
    assert files['refused.jo'] == SAMPLES['refused.jo'].encode() and 'refused.jo' in results[1][2]
    assert files['real/fmt.jo'] != perturbed((ROOT / 'compiler' / 'fmt.jo').read_text()).encode()
