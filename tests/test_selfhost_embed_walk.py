"""Embedded directory entries retain recursive ordering, prefixes and hidden filtering."""
import subprocess
from tests import selfhost_lsp_double
from tests.selfhost_lsp_double import leaf_compilers
from tests.support import ROOT, compiler  # noqa: F401

DRIVER = r'''use 'main.jo'
use 'embed_walk.dewy'
main = ():
    out: str[] = ["existing"]
    embed_dir_walk(args()[1], "assets/", mut out)
    loop name in out: print(name)
'''


def test_embed_walk_matches_twin(compiler, tmp_path, monkeypatch):
    root = tmp_path / 'assets'
    (root / 'b').mkdir(parents=True)
    (root / '.hidden').mkdir()
    for name in ('z.txt', 'a.txt', 'b/2.txt', 'b/1.txt', '.skip', '.hidden/nested', 'b/.skip'):
        (root / name).write_text(name)
    monkeypatch.setenv('DEWY_CORE_LIB', str(ROOT / 'lib'))
    monkeypatch.setattr(selfhost_lsp_double, 'DRIVER', DRIVER)
    binaries = leaf_compilers(compiler, tmp_path, ('embed_walk',))
    outputs = [subprocess.run([b, root], capture_output=True, timeout=60) for b in binaries]
    assert all(r.returncode == 0 for r in outputs), [(r.returncode, r.stderr) for r in outputs]
    assert (outputs[0].stdout, outputs[0].stderr) == (outputs[1].stdout, outputs[1].stderr)
    assert outputs[0].stdout == b'existing\nassets/a.txt\nassets/b/1.txt\nassets/b/2.txt\nassets/z.txt\n'
