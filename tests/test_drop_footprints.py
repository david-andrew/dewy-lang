"""A program declaring a drop hook keeps its proofs: 95_kv_store with an unused hook."""
import shutil
import subprocess
from pathlib import Path

from tests.support import compiler

LADDER = Path(__file__).parent / 'ladder' / '95_kv_store'
DUMMY = '''
Dummy = type of [id:int64
    $__drop__
    release = ():>void => {}
]
'''


def test_kv_store_proves_with_drop_hook(compiler, tmp_path):
    copy = tmp_path / 'kv'
    shutil.copytree(LADDER, copy)
    design = copy / 'design.dewy'
    design.write_text(design.read_text() + DUMMY)
    checked = subprocess.run([compiler, 'check', 'design.dewy'], cwd=copy, capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    assert ': error:' not in checked.stderr, checked.stderr
