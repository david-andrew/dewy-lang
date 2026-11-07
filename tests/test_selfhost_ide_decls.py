"""Editor indexing (declarations, references, hints, completion details), call-trail notes, Dewy
spellings in messages and next-error reruns agree with frozen Jo."""
import subprocess

from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401
from tests.test_selfhost_lsp_ops import compare_session

PROGRAMS = {
    # (an error inside a generic instance: the note names the instance's signature)
    'trail.dewy': 'add=(a @b)=>a and "x"\nmain=()=>{\n    let z=2\n    printl(add(1 @z))\n}\n',
    # (errors in two functions: the second is found by a rerun without the first's body)
    'skips.dewy': 'helper=(a:int64)=>{\n    let q:int64="no"\n    a\n}\nother=()=>{\n    let r:string=5\n}\n'
                  'main=()=>printl(helper(1))\n',
    # (a library name spelled the Dewy way in the message)
    'alt.dewy': 'main=()=>{\n    let xs=[1 2]\n    xs.remove(0)\n}\n',
    'clean.dewy': 'Point:type=[x:float64 y:float64]\nmain=()=>{\n    let p=Point[1.0 2.0]\n    printl("{p.x}")\n}\n',
}


def test_ide_decls_session(compiler, tmp_path, monkeypatch):
    assert '"label"' in compare_session(compiler, tmp_path, monkeypatch, ('ide_decls',))


def test_ide_decls_messages(compiler, tmp_path, monkeypatch):
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    dewy, jo = leaf_compilers(compiler, tmp_path, ('ide_decls',))
    for name, text in PROGRAMS.items():
        (tmp_path / name).write_text(text)
    outputs = []
    for binary in (dewy, jo):
        runs = [subprocess.run([binary, 'check', name], cwd=tmp_path, capture_output=True, text=True,
                               timeout=120, check=False) for name in PROGRAMS]
        outputs.append([(r.returncode, r.stdout, r.stderr.replace(str(binary), 'dewy-core')) for r in runs])
    assert outputs[0] == outputs[1]
    trail, skips, alt, clean = outputs[1]
    assert 'note: in add(a:int @b:int), called here' in trail[2]
    assert 'expected int64, found string' in skips[2] and 'expected string, found int' in skips[2]
    assert '`xs.pop(i)`' in alt[2] and clean[0] == 0
