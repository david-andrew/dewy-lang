"""The reusable native driver follows the CLI's absolute module identities."""
import os
from pathlib import Path
import subprocess

from test_bootstrap_structural_text import build_program_driver

ROOT = Path(__file__).resolve().parents[2]


def test_native_driver_accepts_mixed_path_spellings(tmp_path):
    driver=build_program_driver(tmp_path)
    entry=tmp_path/'entry.dewy'
    system=ROOT/'library/system.dewy'
    entry.write_text(f'from p"{os.path.relpath(system,tmp_path)}" import Arena\nmain=():>int64=>42\n')
    relative=os.path.relpath(entry,ROOT)
    first=None
    for index,(source,library) in enumerate([(relative,ROOT/'library'),(entry,'library'),(relative,'library')]):
        result=subprocess.run([driver,source,library,tmp_path/'cache'],cwd=ROOT,
                              env={**os.environ,'DEWY_TEST_PRELUDE_CACHE':'miss' if index==0 else 'hit'},
                              capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stdout+result.stderr
        if first is None:first=result.stdout
        else:assert result.stdout==first
