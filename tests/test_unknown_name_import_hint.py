"""An unknown name defined in a file the program has but this one does not import: a Dewy file is
told Dewy's import form, a Sloppy file Sloppy's `use`."""
import subprocess

from tests.support import compiler  # noqa: F401


def test_dewy_file_gets_dewy_import_hint(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'helpers.dewy').write_text('advance = (x:int64) => x + 1\n')
    (tmp_path / 'other.dewy').write_text('import p"helpers.dewy" as h\n')
    source = tmp_path / 'main.dewy'
    source.write_text('import p"other.dewy"\nmain = () => {\n    printl(advance(1))\n}\n')
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode != 0
    assert '`from p"helpers.dewy" import advance` at its top' in checked.stderr, checked.stderr
    assert "use '" not in checked.stderr, checked.stderr


def test_jo_file_keeps_use_hint(compiler, tmp_path):  # noqa: F811
    (tmp_path / 'helpers.jo').write_text('advance = (x: int) -> int: x + 1\n')
    (tmp_path / 'other.jo').write_text("use 'helpers.jo'\n")
    source = tmp_path / 'main.jo'
    source.write_text("use 'other.jo'\nmain = ():\n    print(advance(1))\n")
    checked = subprocess.run([compiler, 'check', source], capture_output=True, text=True, timeout=60, check=False)
    assert checked.returncode != 0
    assert "`use 'helpers.jo'` at its top" in checked.stderr, checked.stderr
