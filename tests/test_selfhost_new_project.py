"""`new`: project names and files, and each refusal, match frozen Jo."""
import shutil

import pytest

from tests.selfhost_narrow import compare_narrow
from tests.support import compiler  # noqa: F401

KINDS = ('game', 'arcade', 'platformer', '3d', 'story', 'online', 'program')

DRIVER = r'''
main = ():
    loop dir in ["game", "My Game/", "a\\b\\Café__x///", "/", "", "---", "-a-", "A B  C", "x.y", "é"]:
        print("[{new_project_name(dir, "fallback")}]")
    a = args()
    if a.len() > 1: new_project(a[1], a)
'''


def files(directory):
    return sorted((str(p.relative_to(directory)), p.read_bytes() if p.is_file() else None)
                  for p in directory.rglob('*'))


@pytest.mark.parametrize('release', [False, True], ids=['default', 'release'])
def test_new_project_twins(compiler, tmp_path, release):  # noqa: F811
    run = tmp_path / 'run'

    def fresh():
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir()
        (run / 'taken').mkdir()
        (run / 'blocked').write_text('')
        return run

    library = tmp_path / 'library'
    (library / 'new/dewy').mkdir(parents=True)
    for kind in KINDS:
        (library / f'new/dewy/{kind}.dewy').write_text(f'# {kind}\n')
    (library / 'new/dewy/empty.dewy').write_text('')
    lib = str(library)
    invocations = [((lib, 'Some Project', kind), 0) for kind in KINDS]
    invocations += [((lib, 'default'), 0), ((), 0), ((lib,), 2), ((lib, '-dash'), 2), ((lib, 'x', 'game', 'more'), 2),
                    ((lib, 'taken'), 1), ((lib, 'x', 'nothing'), 2), ((lib, 'x', 'empty'), 2),
                    ((lib + '/gone', 'x'), 1), ((lib, 'blocked/x'), 1)]
    outputs = compare_narrow(compiler, tmp_path, release, ('new_project',), DRIVER, run_in=fresh, observe=files,
                             invocations=invocations)
    assert b'[my-game.dewy]' in outputs[0] and b'[fallback.dewy]' in outputs[0]
    assert b'Created Some Project/main.dewy' in outputs[0]
