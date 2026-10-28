"""Nested comprehension row lengths belong to evaluated snapshots and positions."""
import subprocess
import pytest
from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('construction,change,accepted', [
    ('[loop row in image [loop _ in row false]]', '', True),
    ('[loop row in image [loop _ in row false]]', 'if seen.length >? 0 and seen[0].length >? 0 seen[0][0]=false;', True),
    ('[loop row in image [loop _ in row false]]', 'if seen.length >? 0 seen[0].clear();', False),
    ('[loop row in image [loop _ in row false]]', 'if image.length >? 0 image[0].push(9);', False),
    ('[loop row in image [loop _ in row if false false]]', '', False),
    ('[loop row in image if row.length >? 0 [loop _ in row false]]', '', False),
    ('[loop row in image [false]]', '', False),
])
def test_matching_rows(compiler, tmp_path, construction, change, accepted):
    source = tmp_path / 'rows.dewy'
    source.write_text('probe=(image:array<array<int>>)=>{'
                      f'let seen={construction}; {change}'
                      'loop y in [0..image.length) '
                      'loop x in [0..image[y].length) seen[y][x]=true; '
                      'printl(seen)}\n'
                      'main=()=>{probe([[1 2] [3] []]); probe([])}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True)
    assert (checked.returncode == 0) == accepted, checked.stdout + checked.stderr
    if not accepted:
        assert 'cannot prove' in checked.stderr
    else:
        binary = tmp_path / 'rows'
        built = subprocess.run([compiler, 'build', source, '-o', binary], capture_output=True, text=True)
        assert built.returncode == 0, built.stderr
        ran = subprocess.run([binary], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        assert ran.stdout == '[[true true] [true] []]\n[]\n'
