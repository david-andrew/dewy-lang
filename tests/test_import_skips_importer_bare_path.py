"""A file named like a library module imports the library, whichever spelling names the file:
`check base64.dewy` from its folder is the same file as ./base64.dewy (LANGUAGE.md, imports)."""
import subprocess

from tests.support import compiler  # noqa: F401


def test_bare_file_name_skips_the_importer(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'base64.dewy').write_text('import base64\nmain = ():>void => { printl"ok" }\n')
    for name in ('base64.dewy', './base64.dewy', str(tmp_path / 'base64.dewy')):
        checked = subprocess.run([compiler, 'check', name], cwd=tmp_path, capture_output=True, text=True,
                                 timeout=60, check=False)
        assert checked.returncode == 0, checked.stderr
        assert 'import cycle' not in checked.stderr, checked.stderr
