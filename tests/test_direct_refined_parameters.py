"""Refined scalar parameters retain the legacy AST with a lazy direct body."""
import os
import subprocess

import pytest

from tests.support import compiler  # noqa: F401


@pytest.mark.parametrize('release', [False, True])
def test_refined_parameter_body(compiler, tmp_path, release):
    source = tmp_path / 'refined.dewy'
    source.write_text('''
bounded=(k:int64<0 <=? k and k <? 63>):>int64=>{
    let value:int64=1 << k
    return value
}
small=(k:uint8<k <? 10>):>uint8=>k+1
main=():>void=>{printl(bounded(5)) printl(small(8))}
''')
    images = []
    for mode in ('old', 'compare'):
        output = tmp_path / mode
        built = subprocess.run([compiler, 'build', source, '-o', output,
                                *(['--release'] if release else [])],
                               env=dict(os.environ, DEWY_FRONTEND=mode),
                               capture_output=True, text=True, timeout=30)
        assert built.returncode == 0, built.stdout + built.stderr
        images.append(output.read_bytes())
        ran = subprocess.run([output], capture_output=True, text=True, timeout=10)
        assert ran.returncode == 0 and ran.stdout == '32\n9\n', ran.stdout + ran.stderr
    assert images[0] == images[1]
